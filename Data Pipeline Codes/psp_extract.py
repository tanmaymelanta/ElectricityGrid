import requests
import urllib3
from pathlib import Path
import os
import contextlib
import camelot
import pandas as pd
import io
import base64
import shutil
from datetime import datetime, timedelta, timezone

# ============================================================
# CONFIG
# ============================================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
API_URL = "https://z7kbg6njuc.execute-api.ap-south-1.amazonaws.com/psp"
API_KEY = os.environ["PSP_API_KEY"]
GITHUB_TOKEN = os.environ["GIT_TOKEN"]

OWNER = "tanmaymelanta"
REPO = "ElectricityGrid"
BRANCH = "main"

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

# ============================================================
# GET DAILY PSP FILE
# ============================================================
def fetch_psp_report(report_date=None):
    if not report_date:
        ist = timezone(timedelta(hours=5, minutes=30))
        report_date = (datetime.now(ist) - timedelta(days=1)).strftime("%Y-%m-%d")

    response = requests.get(
        API_URL,
        params={"date": report_date},
        headers={"x-api-key": API_KEY},
        timeout=40
    )

    if response.status_code == 404:
        raise FileNotFoundError(f"No PSP report found for {report_date}")
    
    response.raise_for_status()
    data = response.json()
    return data

# ============================================================
# DATA EXTRACT
# ============================================================
def generation_source_table_extract(pdf_path, report_date):
    try:
        with open(os.devnull, "w") as f, contextlib.redirect_stderr(f):
            tables = camelot.read_pdf(str(pdf_path),pages="all",flavor="lattice")

        df_pct = None
        final_df = None
        for i in range(len(tables)):
            df = tables[i].df
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)
            if "All India" in df.columns:
                source_replace_dict = {
                    "Coal": "THERMAL",
                    "Lignite": "THERMAL",
                    "Hydro": "HYDRO",
                    "Nuclear": "NUCLEAR",
                    "Gas, Naptha & Diesel": "GAS",
                    "RES (Wind, Solar, Biomass & Others)": "RES"
                }
                df[""] = (df[""].str.strip().replace(source_replace_dict))
                numeric_cols = ["NR","WR","SR","ER","NER","All India","% Share"]
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(),errors="coerce")
                grouped_df = (df.groupby([""]).sum(numeric_only=True).reset_index())
                grouped_df.set_index("", inplace=True)
                source = grouped_df.T.reset_index()
                source = source.rename(columns={0: "REGION"})[:5]
                fuel_cols = ["GAS","HYDRO","NUCLEAR","RES","THERMAL"]
                df_pct = source.copy()
                df_pct[fuel_cols] = (source[fuel_cols] / source[fuel_cols].sum())
              
            if ('15 Min (INSTANTANEOUS) ALL INDIA GRID FREQUENCY, GENERATION & DEMAND MET (SCADA DATA)' in df.columns or '15 Min (INSTANTANEOUS) ALL INDIA GRID FREQUENCY, GENERATION & DEMAND MET' in df.columns):
                if i + 1 < len(tables):
                    next_df = tables[i + 1].df
                    next_df.columns = df.columns
                    df = pd.concat([df, next_df],ignore_index=True)
                df.columns = df.iloc[0]
                df = df.iloc[2:].reset_index(drop=True)

                time_df = (report_date + "T" + df["TIME"])
                time_df = pd.to_datetime(time_df,errors="coerce")

                col_rename_dict = {
                    "NUCLEAR\n(MW)": "NUCLEAR",
                    "NUCLEAR \n(MW)": "NUCLEAR",
                    "NUCLEA\nR\n(MW)": "NUCLEAR",
                    "WIND\n(MW)": "WIND",
                    "WIND \n(MW)": "WIND",
                    "SOLAR\n(MW)": "SOLAR",
                    "SOLAR \n(MW)": "SOLAR",
                    "HYDRO²\n(MW)": "HYDRO",
                    "HYDRO \n(MW)": "HYDRO",
                    "HYDRO**\n(MW)": "HYDRO",
                    "HYDRO*\n*\n(MW)": "HYDRO",
                    "HYDRO\n(MW)": "HYDRO",
                    "GAS \n(MW)": "GAS",
                    "GAS (MW)": "GAS",
                    "GAS\n(MW)": "GAS",
                    "THERMA\nL\n(MW)": "THERMAL",
                    "THERMAL\n(MW)": "THERMAL",
                    "THERM\nAL\n(MW)": "THERMAL",
                    "THERMAL \n(MW)": "THERMAL"
                }
                hf_df = df.rename(columns=col_rename_dict)
                numeric_cols = ['NUCLEAR', 'WIND','SOLAR', 'HYDRO', 'GAS', 'THERMAL']
                for col in numeric_cols:
                    hf_df[col] = pd.to_numeric(hf_df[col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
                hf_df = hf_df[numeric_cols]
                hf_df = hf_df * 1000 * 15 / 60 # MW → MWh for 15 minutes

                merged_df = hf_df.join(time_df)
                final_df = merged_df[merged_df["TIME"].notna()].drop_duplicates()
        return df_pct, final_df
    except Exception as e:
        print(f"Generation extraction error: {e}")

def source_region_extract(df_pct, final_df,filename):
    direct_mapping = {"NUCLEAR": "NUCLEAR","HYDRO": "HYDRO","GAS": "GAS","THERMAL": "THERMAL"}
    result = final_df.merge(df_pct,how="cross",suffixes=("_india", "_pct"))

    for pct_col, india_col in direct_mapping.items():
        result[india_col] = (result[f"{india_col}_india"] * result[f"{pct_col}_pct"])
    result["WIND"] = (result["WIND"] * result["RES"])
    result["SOLAR"] = (result["SOLAR"] * result["RES"])
    result = result.rename(columns={"TIME": "Time", "REGION": "Region", "NUCLEAR": "Nuclear",
                                    "WIND": "Wind", "SOLAR": "Solar", "HYDRO": "Hydro",
                                    "GAS": "Gas", "THERMAL": "Thermal"})
    result['filename'] = filename
    result = result[["Time","Region","Nuclear","Wind","Solar","Hydro","Gas","Thermal","filename"]]
    return result

def statewise_table_extract(pdf_path, filename,report_date):
    rename_map = {
        'Max. Demand Met \nduring the day \n(MW)': 'Max. Demand Met during the day (MW)',
        'Shortage during \nmaximum Demand \n(MW)': 'Shortage during maximum Demand (MW)',
        'Energy\nMet (MU)': 'Energy Met (MU)',
        'Drawal\nSchedule (MU)': 'Drawal Schedule (MU)',
        'OD(+)/\nUD(-) (MU)': 'OD(+)/UD(-) (MU)',
        'Max\nOD (MW)': 'Max OD (MW)',
        'RegionRegion': 'Region'
    }

    try:
        with open(os.devnull, "w") as f, contextlib.redirect_stderr(f):
            tables = camelot.read_pdf(str(pdf_path),pages="all",flavor="lattice")
        for table in tables:
            df = table.df
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)
            if "States" in df.columns:
                state = df.rename(columns=rename_map, errors="ignore")
                state["Region"] = (state["Region"].replace("", pd.NA).ffill())
                state["filename"] = filename
                state["report_date"] = report_date
                return state
        return None
    except Exception as e:
        print(f"Statewise extraction error: {e}")

# ============================================================
# GITHUB UPLOADS
# ============================================================
def github_request_files(folder):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/git/trees/{BRANCH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}","Accept": "application/vnd.github+json"}
    params = {"recursive": 1}

    response = requests.get(url,headers=headers,params=params,timeout=30)
    response.raise_for_status()
    tree = response.json()
    if tree.get("truncated"):
        raise Exception("Repository tree exceeds GitHub API limit.")
    
    processed_files = []
    prefix = folder.rstrip("/") + "/"
    for item in tree["tree"]:
        if item["type"] != "blob":
            continue
        path = item["path"]
        if path.startswith(prefix) and path.endswith(".parquet"):
            processed_files.append(path[len(prefix):].removesuffix(".parquet"))
    return processed_files

def github_upload_parquet(df,folder,report_date):
    buffer = io.BytesIO()
    df.to_parquet(buffer,index=False,engine="pyarrow")
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("utf-8")

    path = f"{folder}/{report_date}.parquet"
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}","Accept": "application/vnd.github+json"}
    payload = {"message": f"Add {report_date}.parquet","content": encoded,"branch": BRANCH}

    response = requests.put(url,headers=headers,json=payload,timeout=60)
    response.raise_for_status()
    print(f"Uploaded: {path}")

def main():
    data = fetch_psp_report()
    report_date = data["report_date"]
    filename = data["title"]
    
    pdf_bytes = base64.b64decode(data.pop("pdf_base64"))
    pdf_path = TEMP_DIR / f"{filename}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    processed_files = github_request_files(folder="Source Generation Regionwise")
    if report_date not in processed_files:
        try:
            df_pct, final_df = generation_source_table_extract(pdf_path=pdf_path,report_date=report_date)
            source_region_df = source_region_extract(df_pct=df_pct,final_df=final_df,filename=filename)
            github_upload_parquet(df=source_region_df,folder="Source Generation Regionwise",report_date=report_date)
        except Exception as e:
            print(e)

    processed_files = github_request_files(folder="Power Supply Statewise")
    if report_date not in processed_files:
        try:
            statewise = statewise_table_extract(pdf_path=pdf_path,filename=filename,report_date=report_date)
            github_upload_parquet(df=statewise,folder="Power Supply Statewise",report_date=report_date)
        except Exception as e:
            print(e)
    
    shutil.rmtree(TEMP_DIR,ignore_errors=True)

if __name__ == "__main__":
    main()
