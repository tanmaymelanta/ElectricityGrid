import pandas as pd
import glob
import os
import re
from sqlalchemy import create_engine, text

# ============================================================
# CONFIGURATION
# ============================================================
FOLDER_PATH = "Source Generation Regionwise"
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

# ============================================================
# MAIN ETL
# ============================================================
def source_generation_etl():
    CANONICAL_MAP = [
        (r"^time$", "Time"),
        (r"^region$", "Region"),
        (r"^nuclear$", "Nuclear"),
        (r"^wind$", "Wind"),
        (r"^solar$", "Solar"),
        (r"^hydro$", "Hydro"),
        (r"^gas$", "Gas"),
        (r"^thermal$", "Thermal"),
        (r"^filename$", "filename"),
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
        
    dfs = []
    for f in parquet_files:
        print(f"Reading: {os.path.basename(f)}")
        df = pd.read_parquet(f)
        df.columns = [clean_col(c) for c in df.columns]

        df.columns = [map_to_canonical(c,CANONICAL_MAP) for c in df.columns]
        df = coalesce_duplicate_columns(df)
        if "filename" not in df.columns:
            df["filename"] = os.path.basename(f)
        dfs.append(df)

    combined_df = pd.concat(dfs,ignore_index=True)

    required_columns = ["Time","Region","filename"]
    measure_columns = ["Nuclear","Wind","Solar","Hydro","Gas","Thermal"]
    missing_required_columns = [col for col in required_columns if col not in combined_df.columns]
    if missing_required_columns:
        raise ValueError(f"Missing mandatory columns: {missing_required_columns}")

    for col in measure_columns:
        if col not in combined_df.columns:
            combined_df[col] = None

    columns_to_keep = (required_columns + measure_columns)
    final_df = combined_df[columns_to_keep].copy()
    final_df["Region"] = (final_df["Region"].astype(str).str.strip().str.upper())
    final_df["Time"] = pd.to_datetime(final_df["Time"],errors="coerce")
    
    invalid_times = final_df[final_df["Time"].isna()]
    if not invalid_times.empty:
        raise ValueError(f"Invalid Time values found:\n {invalid_times.head(20)}")

    numeric_mapping = {"Nuclear":"nuclear","Wind":"wind","Solar":"solar","Hydro":"hydro","Gas":"gas","Thermal":"thermal"}
    for source_column in numeric_mapping:
        final_df[source_column] = pd.to_numeric(final_df[source_column],errors="coerce")
    
    duplicate_grain = (final_df.groupby(["Time","Region"],dropna=False).size().reset_index(name="row_count"))
    duplicates = duplicate_grain[duplicate_grain["row_count"] > 1]
    if not duplicates.empty:
        final_df.drop_duplicates(subset=None, keep='first', inplace=False, ignore_index=False)
        duplicate_grain = (final_df.groupby(["Time","Region"],dropna=False).size().reset_index(name="row_count"))
        duplicates = duplicate_grain[duplicate_grain["row_count"] > 1]
    if not duplicates.empty:
        raise ValueError(f"Duplicate source generation grain detected before dimension lookup:\n{duplicates}")

    region_lookup = pd.read_sql("""SELECT region_key, UPPER(TRIM(region_name)) AS region_name FROM warehouse.dim_region""",engine)
    final_df = final_df.merge(region_lookup,left_on="Region",right_on="region_name",how="left")
    missing_regions = final_df[final_df["region_key"].isna()]
    if not missing_regions.empty:
        raise ValueError(f"Some regions do not exist in warehouse.dim_region:\n{missing_regions[['Region']].drop_duplicates()}")

    fact_df = final_df[["Time","region_key","Nuclear","Wind","Solar","Hydro","Gas","Thermal","filename"]].copy()
    fact_df = fact_df.rename(columns={"Time": "generation_time", "Nuclear": "nuclear", "Wind": "wind", "Solar": "solar", "Hydro": "hydro", "Gas": "gas", "Thermal": "thermal", "filename": "source_filename"})
    fact_df = fact_df.where(pd.notnull(fact_df),None)
    staging_table = ("stg_fact_source_generation")

    with engine.begin() as connection:
        connection.execute(text(f"""DROP TABLE IF EXISTS warehouse.{staging_table}"""))
        connection.execute(
            text(
                f"""
                CREATE TABLE warehouse.{staging_table} AS
                SELECT *
                FROM warehouse.fact_source_generation
                WITH NO DATA
                """
            )
        )
        fact_df.to_sql(staging_table,connection,schema="warehouse",if_exists="append",index=False,method="multi",chunksize=1000)
        connection.execute(
            text(
                f"""
                DELETE FROM
                    warehouse.fact_source_generation f
                USING (
                    SELECT DISTINCT
                        source_filename
                    FROM
                        warehouse.{staging_table}
                ) s
                WHERE
                    f.source_filename =
                    s.source_filename
                """
            )
        )
        connection.execute(
            text(
                f"""
                INSERT INTO
                    warehouse.fact_source_generation (
                        generation_time,
                        region_key,
                        nuclear,
                        wind,
                        solar,
                        hydro,
                        gas,
                        thermal,
                        source_filename
                    )
                SELECT
                    generation_time,
                    region_key,
                    nuclear,
                    wind,
                    solar,
                    hydro,
                    gas,
                    thermal,
                    source_filename
                FROM
                    warehouse.{staging_table}
                """
            )
        )
        connection.execute(text(f"""DROP TABLE warehouse.{staging_table}"""))
        print("DATABASE LOAD SUCCESSFUL")

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    source_generation_etl()
