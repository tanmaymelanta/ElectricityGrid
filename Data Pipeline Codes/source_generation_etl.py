import pandas as pd
import glob
import os
import re
from sqlalchemy import create_engine, text


# ============================================================
# CONFIG
# ============================================================

FOLDER_PATH = "Source Generation Regionwise"
DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

# ============================================================
# SOURCE GENERATION ETL
# ============================================================

def source_generation_etl():

    # --------------------------------------------------------
    # 1. Find parquet files
    # --------------------------------------------------------

    parquet_files = glob.glob(
        os.path.join(FOLDER_PATH, "*.parquet")
    )

    if not parquet_files:
        print("No parquet files found.")
        return

    print(f"Found {len(parquet_files)} parquet files")


    # --------------------------------------------------------
    # 2. Read all parquet files
    # --------------------------------------------------------

    dfs = []

    for file in parquet_files:

        print(f"Reading: {file}")

        df = pd.read_parquet(file)

        # ----------------------------------------------------
        # Standardize column names
        # ----------------------------------------------------

        df.columns = [
            str(col).strip().replace("\n", " ")
            for col in df.columns
        ]

        # ----------------------------------------------------
        # Rename columns to warehouse naming convention
        # ----------------------------------------------------

        rename_map = {
            "Time": "generation_time",
            "Region": "Region",
            "Nuclear": "nuclear",
            "Wind": "wind",
            "Solar": "solar",
            "Hydro": "hydro",
            "Gas": "gas",
            "Thermal": "thermal",
            "filename": "source_filename"
        }

        df = df.rename(columns=rename_map)

        # ----------------------------------------------------
        # Add filename if source file doesn't contain it
        # ----------------------------------------------------

        if "source_filename" not in df.columns:
            df["source_filename"] = os.path.basename(file)

        dfs.append(df)


    # --------------------------------------------------------
    # 3. Combine files
    # --------------------------------------------------------

    combined_df = pd.concat(
        dfs,
        ignore_index=True
    )

    print(f"Total source rows: {len(combined_df)}")


    # --------------------------------------------------------
    # 4. Validate required columns
    # --------------------------------------------------------

    required_columns = [
        "generation_time",
        "Region",
        "source_filename"
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in combined_df.columns
    ]

    if missing_columns:

        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )


    # --------------------------------------------------------
    # 5. Make sure generation columns exist
    # --------------------------------------------------------

    generation_columns = [
        "nuclear",
        "wind",
        "solar",
        "hydro",
        "gas",
        "thermal"
    ]

    for col in generation_columns:

        if col not in combined_df.columns:

            print(
                f"WARNING: {col} not present. "
                f"Creating NULL column."
            )

            combined_df[col] = None


    # --------------------------------------------------------
    # 6. Clean Region
    # --------------------------------------------------------

    combined_df["Region"] = (
        combined_df["Region"]
        .astype(str)
        .str.strip()
        .str.upper()
    )


    # --------------------------------------------------------
    # 7. Convert Time to datetime
    # --------------------------------------------------------

    combined_df["generation_time"] = pd.to_datetime(
        combined_df["generation_time"],
        errors="coerce"
    )

    invalid_time = combined_df["generation_time"].isna().sum()

    if invalid_time > 0:

        raise ValueError(
            f"Found {invalid_time} rows with invalid generation_time"
        )


    # --------------------------------------------------------
    # 8. Convert generation measures to numeric
    # --------------------------------------------------------

    for col in generation_columns:

        combined_df[col] = pd.to_numeric(
            combined_df[col],
            errors="coerce"
        )


    # --------------------------------------------------------
    # 9. Select final columns
    # --------------------------------------------------------

    final_df = combined_df[
        [
            "generation_time",
            "Region",
            "nuclear",
            "wind",
            "solar",
            "hydro",
            "gas",
            "thermal",
            "source_filename"
        ]
    ].copy()


    # --------------------------------------------------------
    # 10. Check duplicate grain
    #
    # Grain:
    # generation_time + Region
    # --------------------------------------------------------

    duplicates = final_df[
        final_df.duplicated(
            subset=[
                "generation_time",
                "Region"
            ],
            keep=False
        )
    ]

    if not duplicates.empty:

        print(
            f"WARNING: Found {len(duplicates)} rows "
            f"with duplicate generation_time + Region"
        )

        # ----------------------------------------------------
        # If source contains duplicate rows for same
        # generation_time + Region, aggregate them.
        # ----------------------------------------------------

        agg_dict = {
            "nuclear": "sum",
            "wind": "sum",
            "solar": "sum",
            "hydro": "sum",
            "gas": "sum",
            "thermal": "sum",
            "source_filename": "first"
        }

        final_df = (
            final_df
            .groupby(
                [
                    "generation_time",
                    "Region"
                ],
                as_index=False
            )
            .agg(agg_dict)
        )


    # --------------------------------------------------------
    # 11. Load region dimension
    # --------------------------------------------------------

    region_query = text("""
        SELECT
            region_key,
            region_name
        FROM warehouse.dim_region
    """)

    region_df = pd.read_sql(
        region_query,
        engine
    )

    region_df["region_name"] = (
        region_df["region_name"]
        .astype(str)
        .str.strip()
        .str.upper()
    )


    # --------------------------------------------------------
    # 12. Join with dim_region
    # --------------------------------------------------------

    final_df = final_df.merge(
        region_df,
        left_on="Region",
        right_on="region_name",
        how="left"
    )


    # --------------------------------------------------------
    # 13. Validate region lookup
    # --------------------------------------------------------

    missing_regions = final_df[
        final_df["region_key"].isna()
    ]["Region"].drop_duplicates().tolist()

    if missing_regions:

        raise ValueError(
            "The following regions were not found "
            f"in warehouse.dim_region: {missing_regions}"
        )


    # --------------------------------------------------------
    # 14. Build fact dataframe
    # --------------------------------------------------------

    fact_df = final_df[
        [
            "generation_time",
            "region_key",
            "nuclear",
            "wind",
            "solar",
            "hydro",
            "gas",
            "thermal",
            "source_filename"
        ]
    ].copy()


    # --------------------------------------------------------
    # 15. Convert numpy NaN to None
    # --------------------------------------------------------

    fact_df = fact_df.where(
        pd.notnull(fact_df),
        None
    )


    # --------------------------------------------------------
    # 16. Load to staging table
    # --------------------------------------------------------

    staging_table = "staging_source_generation"

    print(
        f"Writing {len(fact_df)} rows to "
        f"staging.{staging_table}"
    )

    fact_df.to_sql(
        staging_table,
        engine,
        schema="staging",
        if_exists="replace",
        index=False,
        method="multi"
    )


    # --------------------------------------------------------
    # 17. UPSERT into fact table
    # --------------------------------------------------------

    upsert_sql = text("""
        INSERT INTO warehouse.fact_source_generation (
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
        FROM staging.staging_source_generation

        ON CONFLICT (
            generation_time,
            region_key
        )
        DO UPDATE SET

            nuclear = EXCLUDED.nuclear,
            wind = EXCLUDED.wind,
            solar = EXCLUDED.solar,
            hydro = EXCLUDED.hydro,
            gas = EXCLUDED.gas,
            thermal = EXCLUDED.thermal,
            source_filename = EXCLUDED.source_filename;
    """)


    with engine.begin() as connection:

        connection.execute(upsert_sql)


    print(
        "Source generation ETL completed successfully."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    source_generation_etl()
