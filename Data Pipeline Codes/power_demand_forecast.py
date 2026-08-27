import os
import pandas as pd
from sqlalchemy import create_engine, text
from prophet import Prophet

# ============================================================
# CONFIGURATION
# ============================================================
DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
FORECAST_END_DATE = pd.Timestamp("2030-12-31")

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def load_historical_data():
    query = """
        SELECT
            report_date,
            region_key,
            region_name,
            state_key,
            state_name,
            entity_type,
            energy_met_mu,
            energy_shortage_mu
        FROM warehouse.vw_state_power_supply
        WHERE entity_type = 'STATE'
            AND report_date >= '2017-05-09'
        ORDER BY report_date
    """
    df = pd.read_sql(query, engine)
    if df.empty:
        raise ValueError("No historical data found.")
    df["report_date"] = pd.to_datetime(df["report_date"])
    return df

def create_demand(df):
    df["estimated_demand_mu"] = df["energy_met_mu"].fillna(0) + df["energy_shortage_mu"].fillna(0)
    return df

def forecast_series(historical_df,forecast_level,region_key=None,state_key=None):
    df = historical_df.copy()
    if forecast_level == "STATE":
        df = df[df["state_key"] == state_key]
    elif forecast_level == "REGION":
        df = df[df["region_key"] == region_key]
    elif forecast_level == "INDIA":
        pass

    daily = df.groupby("report_date", as_index=False)["estimated_demand_mu"].sum()
    daily = daily.rename(columns={"report_date": "ds","estimated_demand_mu": "y"})
    daily = daily.dropna(subset=["ds", "y"])
    daily = daily.sort_values("ds")

    if len(daily) < 365:
        print(
            f"Skipping {forecast_level} "
            f"region={region_key} "
            f"state={state_key} "
            f"because only {len(daily)} observations exist."
        )
        return None

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.95
    )
    model.fit(daily)
    last_date = daily["ds"].max()
    days_to_forecast = (FORECAST_END_DATE - last_date).days

    if days_to_forecast <= 0:
        print(
            f"No future dates required for "
            f"{forecast_level} "
            f"region={region_key} "
            f"state={state_key}"
        )
        return None

    future = model.make_future_dataframe(periods=days_to_forecast,freq="D")
    forecast = model.predict(future)
    forecast = forecast[forecast["ds"] > last_date][["ds","yhat","yhat_lower","yhat_upper"]].copy()
    forecast["forecast_level"] = forecast_level
    forecast["region_key"] = region_key
    forecast["state_key"] = state_key
    forecast["model_name"] = "Prophet"
    forecast = forecast.rename(columns={"ds": "forecast_date","yhat": "predicted_demand_mu","yhat_lower": "lower_bound_mu","yhat_upper": "upper_bound_mu"})
    return forecast

def create_india_forecast(df):
    print("Creating INDIA forecast...")
    return forecast_series(historical_df=df,forecast_level="INDIA")

def create_region_forecasts(df):
    forecasts = []
    region_keys = df["region_key"].dropna().unique()

    for region_key in region_keys:
        print(f"Creating REGION forecast: {region_key}")
        result = forecast_series(historical_df=df,forecast_level="REGION",region_key=int(region_key))
        if result is not None:
            forecasts.append(result)
    if forecasts:
        return pd.concat(forecasts,ignore_index=True)
    return pd.DataFrame()

def create_state_forecasts(df):
    forecasts = []
    state_mapping = df[["region_key","state_key"]].dropna().drop_duplicates()

    for _, row in state_mapping.iterrows():
        region_key = int(row["region_key"])
        state_key = int(row["state_key"])
        print(f"Creating STATE forecast: region={region_key}, state={state_key}")
        result = forecast_series(historical_df=df,forecast_level="STATE",region_key=region_key,state_key=state_key)
        if result is not None:
            forecasts.append(result)
    if forecasts:
        return pd.concat(forecasts,ignore_index=True)
    return pd.DataFrame()

def load_forecast(df):
    with engine.begin() as connection:
        connection.execute(text(""" DELETE FROM warehouse.fact_power_demand_forecast"""))    
    df.to_sql("fact_power_demand_forecast",engine,schema="warehouse",if_exists="append",index=False,method="multi")

# ============================================================
# MAIN
# ============================================================
def main():
    df = load_historical_data()
    df = create_demand(df)

    india_forecast = create_india_forecast(df)
    region_forecast = create_region_forecasts(df)
    state_forecast = create_state_forecasts(df)

    forecasts = [x for x in [india_forecast, region_forecast, state_forecast] if x is not None and not x.empty]
    if not forecasts:
        raise ValueError("No forecasts were generated.")
    final_forecast = pd.concat(forecasts,ignore_index=True)

    final_forecast["forecast_date"] = pd.to_datetime(final_forecast["forecast_date"]).dt.date
    numeric_columns = ["predicted_demand_mu","lower_bound_mu","upper_bound_mu"]
    for col in numeric_columns:
        final_forecast[col] = pd.to_numeric(final_forecast[col],errors="coerce")
    final_forecast = final_forecast[["forecast_date","region_key","state_key","forecast_level","predicted_demand_mu","lower_bound_mu","upper_bound_mu","model_name"]]
    
    load_forecast(final_forecast)
    print("Forecast pipeline completed successfully.")

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    main()
