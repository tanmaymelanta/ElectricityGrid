import pandas as pd
import glob
import os
import re
from sqlalchemy import create_engine

# ============================================================
# CONFIGURATION
# ============================================================
FOLDER_PATH = "Power Supply Statewise"

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def clean_col(col):
    col = str(col).replace("\n", " ")
    col = re.sub(r"\s+", " ", col).strip()
    col = re.sub(r"[¹²³*]", "", col)
    return col.strip()

def map_to_canonical(col, CANONICAL_MAP):
    c = col.lower()
    for pattern, canonical in CANONICAL_MAP:
        if re.search(pattern, c):
            return canonical
    return col

def coalesce_duplicate_columns(df):
    if not df.columns.duplicated().any():
        return df
    new_df = pd.DataFrame(index=df.index)
    for col in df.columns.unique():
        subset = df.loc[:, df.columns == col]
        if subset.shape[1] > 1:
            new_df[col] = subset.bfill(axis=1).iloc[:, 0]
        else:
            new_df[col] = subset.iloc[:, 0]
    return new_df

def get_entity_type(state):
    if state == "Railways":
        return "RAILWAYS"
    elif state == "Other":
        return "OTHER"
    else:
        return "STATE"

# ============================================================
# MAIN FUNCTIONS
# ============================================================
def power_supply_etl():
    CANONICAL_MAP = [
        (r"^region$", "Region"),
        (r"^states?$", "State"),
        (r"max.*demand.*met.*day", "Max Demand Met During the Day (MW)"),
        (r"shortage.*max.*demand|shortage.*peak", "Shortage during Max Demand (MW)"),
        (r"energy met", "Energy Met (MU)"),
        (r"drawal schedule", "Drawal Schedule (MU)"),
        (r"^ud\(-\)", "UD(-) (MU)"),
        (r"od\(\+\)\s*/?\s*ud\(\s*-\s*\)", "OD(+)/UD(-) (MU)"),
        (r"max\s*od", "Max OD (MW)"),
        (r"energy shortage", "Energy Shortage (MU)"),
        (r"^filename$", "filename"),
        (r"^report_date$", "report_date"),
    ]
    parquet_files = glob.glob(os.path.join(FOLDER_PATH, "*.parquet"))

    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found in: {FOLDER_PATH}")

    # ============================== MERGE ALL PARQUETS ==============================
    dfs = []
    for f in parquet_files:
        print(f"Reading: {os.path.basename(f)}")
        df = pd.read_parquet(f)
        df.columns = [clean_col(c) for c in df.columns]
        df.columns = [map_to_canonical(c,CANONICAL_MAP) for c in df.columns]
        df = coalesce_duplicate_columns(df)
        dfs.append(df)
    combined_df = pd.concat(dfs, ignore_index=True)
    # ============================== COLUMN VALIDATION ==============================
    required_columns = ["report_date","Region","State","filename"]
    measure_columns = ["Energy Met (MU)","Max Demand Met During the Day (MW)","Drawal Schedule (MU)","Energy Shortage (MU)","OD(+)/UD(-) (MU)"]
    missing_required_columns = [col for col in required_columns if col not in combined_df.columns]
    if missing_required_columns:
        raise ValueError(f"Missing mandatory columns: {missing_required_columns}")
    for col in measure_columns:
        if col not in combined_df.columns:
            combined_df[col] = None
    columns_to_keep = (required_columns + measure_columns)
    final_df = combined_df[columns_to_keep].copy()
    # ============================== STATE STANDARDIZATION ==============================
    state_replace_dict = {
        "HP": "Himachal Pradesh",
        "MP": "Madhya Pradesh",
        "UP": "Uttar Pradesh",
        "Arunachal": "Arunachal Pradesh",
        "J&K": "J&K(UT) & Ladakh(UT)",
        "J&K(UT) &": "J&K(UT) & Ladakh(UT)",
        "J&K(UT) & \nLadakh(UT)": "J&K(UT) & Ladakh(UT)",
        "J&K(UT) and Ladakh(UT)": "J&K(UT) & Ladakh(UT)",
        "Pondy": "Puducherry",
        "DD": "Diu, Daman & Dadra Nagar Haveli",
        "DNH": "Diu, Daman & Dadra Nagar Haveli",
        "DNHDDPDCL": "Diu, Daman & Dadra Nagar Haveli",

        "AMNSIL": "Other",
        "BALCO": "Other",
        "Bulk Consumer_NR ISTS": "Other",
        "DVC": "Other",
        "Essar steel": "Other",
        "RIL Jamnagar": "Other",
        "RIL JAMNAGAR": "Other",

        "Railways ER ISTS": "Railways",
        "Railways NR ISTS": "Railways",
        "Railways_ER": "Railways",
        "Railways_ER ISTS": "Railways",
        "Railways_NR": "Railways",
        "Railways_NR ISTS": "Railways",
    }
    final_df["State"] = final_df["State"].astype(str).str.strip().replace(state_replace_dict)
    agg_dict = {
        "Energy Met (MU)": "sum",
        "Max Demand Met During the Day (MW)": "max",
        "Drawal Schedule (MU)": "sum",
        "Energy Shortage (MU)": "sum",
        "OD(+)/UD(-) (MU)": "sum",
        "filename": "first"
    }
    grouped_df = final_df.groupby(["report_date", "Region", "State"], as_index=False).agg(agg_dict)
    grouped_df["entity_type"] = grouped_df["State"].apply(get_entity_type)
    # ============================== DATE CLEANUP ==============================
    grouped_df["report_date"] = pd.to_datetime(grouped_df["report_date"],format="%d-%m-%y",errors="coerce").dt.date
    if grouped_df["report_date"].isna().any():
        bad_dates = grouped_df[grouped_df["report_date"].isna()]
        raise ValueError("Invalid report_date values found:\n"f"{bad_dates.head(20)}")
    # ============================== DATA CLEANUP ==============================
    numeric_mapping = {
        "Energy Met (MU)": "energy_met_mu",
        "Max Demand Met During the Day (MW)": "max_demand_met_mw",
        "Drawal Schedule (MU)": "drawal_schedule_mu",
        "Energy Shortage (MU)": "energy_shortage_mu",
        "OD(+)/UD(-) (MU)": "od_ud_mu"
    }
    for source_column in numeric_mapping:
        grouped_df[source_column] = pd.to_numeric(grouped_df[source_column], errors="coerce")
    print(len(grouped_df))
    
if __name__ == "__main__":
    power_supply_etl()
