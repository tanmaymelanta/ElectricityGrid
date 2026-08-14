import io
import base64
import requests
import camelot
from pathlib import Path
import pandas as pd
import contextlib
import os
import warnings
import shutil
warnings.filterwarnings("ignore")

# Folder where temporary PDFs will be downloaded
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

def github_request_files(FOLDER):
    TOKEN = ""
    OWNER = "tanmaymelanta"
    REPO = "ElectricityGenerator"
    BRANCH = "main"

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/git/trees/{BRANCH}"
    headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}
    params = {"recursive": 1}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    tree = response.json()
    if tree.get("truncated"):
        raise Exception("Repository tree exceeds GitHub API limit (100,000 entries).")

    processed_files = []
    prefix = FOLDER.rstrip("/") + "/"
    for item in tree["tree"]:
        if item["type"] != "blob":
            continue
        path = item["path"]
        if path.startswith(prefix) and path.endswith(".parquet"):
            processed_files.append(path[len(prefix):].removesuffix(".parquet"))
    return processed_files

def github_upload_parquet(df, folder, report_date):
    TOKEN = "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"
    OWNER = "tanmaymelanta"
    REPO = "ElectricityGenerator"
    BRANCH = "main"

    # Convert DataFrame to parquet bytes
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("utf-8")

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{folder}/{report_date}.parquet"
    headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}
    payload = {"message": f"Add {report_date}.parquet", "content": encoded, "branch": BRANCH}

    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()
    print(f"Uploaded {report_date}.parquet")

def statewise_table_extract(pdf_url: str, filename,report_date):
    file_name = pdf_url.split("/")[-1]
    pdf_path = TEMP_DIR / file_name

    response = requests.get(pdf_url, timeout=120, verify=False)
    response.raise_for_status()
    pdf_path.write_bytes(response.content)

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
        print(e)

if __name__ == "__main__":
    pdf_df = pd.read_csv(r"C:\Users\tanmayjayanand.m\OneDrive - Synergy Maritime Private Limited\Documents\NLDC Table.csv")

    FOLDER = "Power Supply Statewise"
    processed_files = github_request_files(FOLDER)
    for filename,url,report_date in zip(pdf_df['Description'],pdf_df['URL'],pdf_df['Report Date']):
        try:
            if report_date not in processed_files:
                print(f"Processing {filename}")
                statewise = statewise_table_extract(url,filename,report_date)
                github_upload_parquet(statewise, FOLDER,report_date)
        except Exception as e:
            print(e)
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
