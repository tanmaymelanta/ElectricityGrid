import pandas as pd
import glob
import os
import re
from sqlalchemy import create_engine, text

# ============================================================
# CONFIGURATION
# ============================================================
FOLDER_PATH = "Power Supply Statewise"
DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

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
    changed_files = os.environ.get("CHANGED_FILES", "").strip()
    if changed_files:
        parquet_files = [f.strip() for f in changed_files.splitlines() if f.strip().endswith(".parquet")]
        parquet_files = [f for f in parquet_files if os.path.isfile(f)]
    else:
        parquet_files = glob.glob(os.path.join(FOLDER_PATH, "*.parquet"))
    print(f"Files to process: {len(parquet_files)}")
    if not parquet_files:
        print("No parquet files require processing.")
        return
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
    # ============================== NUMERIC DATA CLEANUP ==============================
    numeric_mapping = {
        "Energy Met (MU)": "energy_met_mu",
        "Max Demand Met During the Day (MW)": "max_demand_met_mw",
        "Drawal Schedule (MU)": "drawal_schedule_mu",
        "Energy Shortage (MU)": "energy_shortage_mu",
        "OD(+)/UD(-) (MU)": "od_ud_mu"
    }
    for source_column in numeric_mapping:
        grouped_df[source_column] = pd.to_numeric(grouped_df[source_column], errors="coerce")
    # ============================== LOAD DIMENSION LOOKUPS ==============================
    date_lookup = pd.read_sql("SELECT date_key, full_date FROM warehouse.dim_date", engine)
    date_lookup["full_date"] = pd.to_datetime(date_lookup["full_date"]).dt.date
    region_lookup = pd.read_sql("SELECT region_key, UPPER(TRIM(region_name)) AS region_name FROM warehouse.dim_region",engine)
    state_lookup = pd.read_sql("SELECT state_key, TRIM(state_name) AS state_name FROM warehouse.dim_state", engine)
    grouped_df = grouped_df.merge(date_lookup, left_on="report_date", right_on="full_date", how="left")
    grouped_df["Region"] = grouped_df["Region"].astype(str).str.strip().str.upper()
    grouped_df = grouped_df.merge(region_lookup, left_on="Region", right_on="region_name", how="left")
    grouped_df["State"] = grouped_df["State"].astype(str).str.strip()
    grouped_df = grouped_df.merge(state_lookup, left_on="State", right_on="state_name", how="left")
    # ============================== DIMENSION TABLE VALIDATION ==============================
    missing_dates = grouped_df[grouped_df["date_key"].isna()]
    if not missing_dates.empty:
        raise ValueError(f"Some report dates do not exist in dim_date:\n{missing_dates[['report_date']].drop_duplicates()}")
    missing_regions = grouped_df[grouped_df["region_key"].isna()]
    if not missing_regions.empty:
        raise ValueError(f"Some regions do not exist in dim_region:\n{missing_regions[['Region']].drop_duplicates()}")
    missing_states = grouped_df[(grouped_df["entity_type"] == "STATE") & (grouped_df["state_key"].isna())]
    if not missing_states.empty:
        raise ValueError(f"Some STATE values do not exist in dim_state:\n{missing_states[['State']].drop_duplicates()}")
    # ============================== GRAIN VALIDATION ==============================
    duplicate_grain = grouped_df.groupby(["date_key","region_key","state_key","entity_type"], dropna=False).size().reset_index(name="row_count")
    duplicates = duplicate_grain[duplicate_grain["row_count"] > 1]
    if not duplicates.empty:
        raise ValueError(f"Duplicate fact grain detected:\n{duplicates}")
    # ============================== FACT TABLE ==============================
    fact_df = grouped_df[["date_key","region_key","state_key","entity_type","Energy Met (MU)","Max Demand Met During the Day (MW)","Drawal Schedule (MU)","Energy Shortage (MU)","OD(+)/UD(-) (MU)","filename"]].copy()
    fact_df = fact_df.rename(
        columns={
            "Energy Met (MU)": "energy_met_mu",
            "Max Demand Met During the Day (MW)": "max_demand_met_mw",
            "Drawal Schedule (MU)": "drawal_schedule_mu",
            "Energy Shortage (MU)": "energy_shortage_mu",
            "OD(+)/UD(-) (MU)": "od_ud_mu",
            "filename": "source_filename"
        }
    )
    fact_df = fact_df.where(pd.notnull(fact_df),None)
    # ============================== LOAD FACT TO DATABASE ==============================
    staging_table = "stg_fact_statepowersupply"
    with engine.begin() as connection:
        connection.execute(text(f"DROP TABLE IF EXISTS warehouse.{staging_table}"))
        connection.execute(text(f"""
            CREATE TABLE warehouse.{staging_table} AS 
            SELECT * FROM warehouse.fact_statepowersupply WITH NO DATA
            """
        ))
        fact_df.to_sql(
            staging_table,
            connection,
            schema="warehouse",
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000
        )
        connection.execute(text(f"""
            DELETE FROM warehouse.fact_statepowersupply f
                USING (
                    SELECT DISTINCT source_filename
                    FROM warehouse.{staging_table}
                ) s
                WHERE f.source_filename = s.source_filename
            """
        ))
        connection.execute(text(f"""
            INSERT INTO warehouse.fact_statepowersupply (
                date_key,
                region_key,
                state_key,
                entity_type,
                energy_met_mu,
                max_demand_met_mw,
                drawal_schedule_mu,
                energy_shortage_mu,
                od_ud_mu,
                source_filename
            )
            SELECT
                date_key,
                region_key,
                state_key,
                entity_type,
                energy_met_mu,
                max_demand_met_mw,
                drawal_schedule_mu,
                energy_shortage_mu,
                od_ud_mu,
                source_filename
            FROM warehouse.{staging_table}
            """
        ))
        connection.execute(text(f"DROP TABLE warehouse.{staging_table}"))   
        print("DATABASE LOAD SUCCESSFUL")
if __name__ == "__main__":
    power_supply_etl()
