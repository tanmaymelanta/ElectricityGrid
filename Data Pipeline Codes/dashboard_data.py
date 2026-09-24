import os
import pandas as pd
from sqlalchemy import create_engine

# ============================== LOAD DATA ==============================
def load_power_supply_data():
    query = """
        SELECT
            report_date,
            region_name,
            state_name,
            entity_type,
            energy_met_mu,
            max_demand_met_mw,
            drawal_schedule_mu,
            energy_shortage_mu,
            od_ud_mu,
            source_filename
        FROM warehouse.vw_state_power_supply
        ORDER BY report_date
    """
    df = pd.read_sql(query, engine)
    df["report_date"] = pd.to_datetime(df["report_date"])
    return df

def load_forecast_data():
    query = """
        SELECT
            forecast_date,
            forecast_level,
            region_key,
            region_name,
            state_key,
            state_name,
            predicted_demand_mu,
            lower_bound_mu,
            upper_bound_mu,
            model_name,
            model_run_date
        FROM warehouse.vw_power_demand_forecast
        ORDER BY forecast_date
    """
    df = pd.read_sql(query, engine)
    df["forecast_date"] = pd.to_datetime(df["forecast_date"])
    return df

def load_minute_data():
    query = """
        SELECT *
        FROM warehouse.vw_generation_minute
        WHERE generation_time >= NOW() - INTERVAL '3 days';
    """
    df = pd.read_sql(query, engine)
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

def load_hourly_data():
    query = """
        SELECT *
        FROM warehouse.vw_generation_hourly
        WHERE generation_time >= NOW() - INTERVAL '7 days';
    """
    df = pd.read_sql(query, engine)
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

def load_daily_data():
    query = """
        SELECT *
        FROM warehouse.vw_generation_daily
        WHERE generation_time >= NOW() - INTERVAL '90 days';
    """
    df = pd.read_sql(query, engine)
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

def load_monthly_data():
    query = """
        SELECT *
        FROM warehouse.vw_generation_monthly
        WHERE generation_time >= NOW() - INTERVAL '12 months';
    """
    df = pd.read_sql(query, engine)
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

def load_yearly_data():
    query = """
        SELECT *
        FROM warehouse.vw_generation_yearly;
    """
    df = pd.read_sql(query, engine)
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

# ============================== DATABASE ==============================
DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

# ============================== OUTPUT ==============================
OUTPUT_DIR = "ElectricityGrid/streamlit_app"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================== EXTRACT ==============================
print("Loading power supply...")
power_supply = load_power_supply_data()
power_supply.to_parquet(f"{OUTPUT_DIR}/power_supply.parquet",index=False)

print("Loading forecast...")
forecast_df = load_forecast_data()
forecast_df.to_parquet(f"{OUTPUT_DIR}/forecast.parquet",index=False)

print("Loading minute...")
minute_df = load_minute_data()
minute_df.to_parquet(f"{OUTPUT_DIR}/minute.parquet",index=False)

print("Loading hourly...")
hourly_df = load_hourly_data()
hourly_df.to_parquet(f"{OUTPUT_DIR}/hourly.parquet",index=False)

print("Loading daily...")
daily_df = load_daily_data()
daily_df.to_parquet(f"{OUTPUT_DIR}/daily.parquet",index=False)

print("Loading monthly...")
monthly_df = load_monthly_data()
monthly_df.to_parquet(f"{OUTPUT_DIR}/monthly.parquet",index=False)

print("Loading yearly...")
yearly_df = load_yearly_data()
yearly_df.to_parquet(f"{OUTPUT_DIR}/yearly.parquet",index=False)

print("All datasets exported successfully.")
