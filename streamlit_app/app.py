import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

# ============================== PAGE CONFIG ==============================
st.set_page_config(
    page_title="India Electric Grid",
    page_icon="⚡",
    layout="wide"
)

# ============================== TITLE ==============================
st.title("⚡ India Electric Grid")
st.caption("Source: GRID-INDIA")

# ============================== LOAD DATA ==============================
@st.cache_data(ttl=3600)
def load_power_supply_data():
    df = pd.read_parquet("power_supply.parquet")
    df["report_date"] = pd.to_datetime(df["report_date"])
    return df

@st.cache_data(ttl=3600)
def load_forecast_data():
    df = pd.read_parquet("forecast.parquet")
    df["forecast_date"] = pd.to_datetime(df["forecast_date"])
    return df

@st.cache_data
def load_emission_factors():
    ef = pd.read_csv(r"C:\Users\tanmayjayanand.m\PycharmProjects\WelcomeScreen\streamlit app\emission_factors.csv")
    ef["source"] = ef["source"].str.strip()
    ef["source_key"] = ef["source"].str.lower()
    ef["lifecycle_ef_gco2eq_kwh"] = pd.to_numeric(ef["lifecycle_ef_gco2eq_kwh"],errors="coerce")
    ef["operational_ef_gco2eq_kwh"] = pd.to_numeric(ef["operational_ef_gco2eq_kwh"],errors="coerce")
    return ef

@st.cache_data(ttl=3600)
def load_minute_data():
    df = pd.read_parquet("minute.parquet")
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

@st.cache_data(ttl=3600)
def load_hourly_data():
    df = pd.read_parquet("hourly.parquet")
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

@st.cache_data(ttl=3600)
def load_daily_data():
    df = pd.read_parquet("daily.parquet")
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

@st.cache_data(ttl=3600)
def load_monthly_data():
    df = pd.read_parquet("monthly.parquet")
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

@st.cache_data(ttl=3600)
def load_yearly_data():
    df = pd.read_parquet("yearly.parquet")
    df["generation_time"] = pd.to_datetime(df["generation_time"])
    return df

power_supply_df = load_power_supply_data()
forecast_df = load_forecast_data()
ef_df = load_emission_factors()

tab1, tab2 = st.tabs(['Power Supply Dashboard', 'Power Source Dashboard'])

with tab1:
    # ============================== POWER SUPPLY HISTORIC DATA ==============================
    st.header("Historical Power Supply")

    # ****************************** HISTORIC UI FILTERS ******************************
    with st.container(border=True):
        regions = sorted(power_supply_df["region_name"].dropna().unique())
        selected_regions = st.multiselect("Region",regions,default=regions)

        states = sorted(power_supply_df["state_name"].dropna().unique())
        selected_states = st.multiselect("State",states)

        min_date = power_supply_df["report_date"].min().date()
        max_date = power_supply_df["report_date"].max().date()
        date_range = st.date_input("Report Date",value=(min_date, max_date),min_value=min_date,max_value=max_date)

    # ****************************** APPLY FILTERS ******************************
    filtered_df = power_supply_df.copy()
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[(filtered_df["report_date"].dt.date >= start_date) & (filtered_df["report_date"].dt.date <= end_date)]

    if selected_regions:
        filtered_df = filtered_df[filtered_df["region_name"].isin(selected_regions)]

    if selected_states:
        filtered_df = filtered_df[filtered_df["state_name"].isin(selected_states)]

    # ****************************** ENERGY MET OVER TIME ******************************
    daily_energy = filtered_df.groupby("report_date", as_index=False)[["energy_met_mu"]].sum()
    daily_energy = daily_energy.rename(columns={"energy_met_mu": "Energy Met (MU)","report_date": "Date"})
    fig = px.line(
        daily_energy,
        x="Date",y=["Energy Met (MU)"],
        title="Energy Consumption Trends"
    )
    fig.update_layout(xaxis_title="Date",yaxis_title="Energy Met (MU)")
    st.plotly_chart(fig,use_container_width=True)

    # ****************************** ENERGY SHORTAGE OVER TIME ******************************
    daily_energy = filtered_df.groupby("report_date", as_index=False)[["energy_shortage_mu", "drawal_schedule_mu"]].sum()
    daily_energy = daily_energy.rename(columns={"energy_shortage_mu": "Energy Shortage (MU)","drawal_schedule_mu": "Drawal Schedule (MU)","report_date": "Date"})
    fig = px.line(
        daily_energy,
        x="Date",y=["Energy Shortage (MU)", "Drawal Schedule (MU)"],
        title="Energy Shortage Trends"
    )
    fig.update_xaxes(range=["2017-05-01", daily_energy["Date"].max()])
    fig.update_yaxes(range=[0, 4000])
    fig.update_layout(xaxis_title="Date",yaxis_title="MU")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ============================== ENERGY DEMAND FORECAST ==============================
    st.header("Forecast Energy Demand")

    # ****************************** FORECAST FILTER UI ******************************
    with st.container(border=True):
        forecast_level = st.selectbox("Forecast Level",["INDIA", "REGION", "STATE"])
        selected_forecast_region = None
        selected_forecast_state = None

        if forecast_level == "REGION":
            forecast_regions = sorted(forecast_df[forecast_df["forecast_level"] == "REGION"]["region_name"].dropna().unique())
            if not forecast_regions:
                st.warning("No regional forecast data available.")
                st.stop()
            selected_forecast_region = st.selectbox("Select Region",forecast_regions)
        elif forecast_level == "STATE":
            forecast_states = sorted(forecast_df[forecast_df["forecast_level"] == "STATE"]["state_name"].dropna().unique())
            if not forecast_states:
                st.warning("No state-level forecast data available.")
                st.stop()
            selected_forecast_state = st.selectbox("Select State",forecast_states)

        # ****************************** FORECAST DATA PREPARATION ******************************
        if forecast_level == "INDIA":
            actual_forecast = power_supply_df[power_supply_df["entity_type"] == "STATE"].copy()
            actual_forecast = actual_forecast.groupby("report_date",as_index=False)[["energy_met_mu","energy_shortage_mu"]].sum()
        elif forecast_level == "REGION":
            actual_forecast = power_supply_df[(power_supply_df["entity_type"] == "STATE") & (power_supply_df["region_name"] == selected_forecast_region)].copy()
            actual_forecast = actual_forecast.groupby("report_date",as_index=False)[["energy_met_mu","energy_shortage_mu"]].sum()
        elif forecast_level == "STATE":
            actual_forecast = power_supply_df[(power_supply_df["entity_type"] == "STATE") & (power_supply_df["state_name"] == selected_forecast_state)][["report_date","energy_met_mu","energy_shortage_mu"]].copy()
        actual_forecast["demand_mu"] = actual_forecast["energy_met_mu"].fillna(0) + actual_forecast["energy_shortage_mu"].fillna(0)

        if forecast_level == "INDIA":
            selected_forecast = forecast_df[forecast_df["forecast_level"] == "INDIA"].copy()
        elif forecast_level == "REGION":
            selected_forecast = forecast_df[(forecast_df["forecast_level"] == "REGION") & (forecast_df["region_name"] == selected_forecast_region)].copy()
        elif forecast_level == "STATE":
            selected_forecast = forecast_df[(forecast_df["forecast_level"] == "STATE") & (forecast_df["state_name"] == selected_forecast_state)].copy()

        # ****************************** FORECAST VISUALIZATION ******************************
        if selected_forecast.empty:
            st.warning("No forecast data available for the selected level.")
            st.stop()

        forecast_min_date = selected_forecast["forecast_date"].min().date()
        forecast_max_date = selected_forecast["forecast_date"].max().date()
        forecast_date_range = st.date_input("Forecast Date Range",value=(forecast_min_date,forecast_max_date),min_value=forecast_min_date,max_value=forecast_max_date)

    if len(forecast_date_range) == 2:
        forecast_start, forecast_end = (forecast_date_range)
        selected_forecast = selected_forecast[(selected_forecast["forecast_date"].dt.date >= forecast_start) & (selected_forecast["forecast_date"].dt.date <= forecast_end)]

    if not selected_forecast.empty:
        first_forecast = selected_forecast.sort_values("forecast_date").iloc[0]
        last_forecast = selected_forecast.sort_values("forecast_date").iloc[-1]
        max_forecast_demand = selected_forecast["predicted_demand_mu"].max()

        col1, col2, col3 = st.columns(3)
        col1.metric("Forecast Start",first_forecast["forecast_date"].strftime("%d %b %Y"))
        col2.metric("Forecast End",last_forecast["forecast_date"].strftime("%d %b %Y"))
        col3.metric("Forecast Demand",f"{max_forecast_demand:,.2f} MU")

    actual_plot = actual_forecast[["report_date","demand_mu"]].copy()
    actual_plot = actual_plot.rename(columns={"report_date": "date","demand_mu": "demand"})
    forecast_plot = selected_forecast[["forecast_date","predicted_demand_mu"]].copy()
    forecast_plot = forecast_plot.rename(columns={"forecast_date": "date","predicted_demand_mu": "demand"})

    # ****************************** FORECAST CHART ******************************
    fig = go.Figure()

    # ACTUAL LINE
    fig.add_trace(
        go.Scatter(
            x=actual_plot["date"],
            y=actual_plot["demand"],
            mode="lines",
            name="Actual Demand",
            line=dict(
                width=2
            )
        )
    )

    # FORECAST LINE
    fig.add_trace(
        go.Scatter(
            x=forecast_plot["date"],
            y=forecast_plot["demand"],
            mode="lines",
            name="Forecast Demand",
            line=dict(
                width=2,
                dash="dash"
            )
        )
    )

    # CONFIDENCE INTERVAL
    if ("lower_bound_mu" in selected_forecast.columns and "upper_bound_mu" in selected_forecast.columns):
        confidence_df = selected_forecast.dropna(subset=["lower_bound_mu","upper_bound_mu"]).copy()
        if not confidence_df.empty:
            confidence_df = confidence_df.sort_values("forecast_date")
            fig.add_trace(
                go.Scatter(
                    x=pd.concat([confidence_df["forecast_date"],confidence_df["forecast_date"].iloc[::-1]]),
                    y=pd.concat([confidence_df["upper_bound_mu"],confidence_df["lower_bound_mu"].iloc[::-1]]),
                    fill="toself",
                    line=dict(width=0),
                    name="Prediction Interval",
                    hoverinfo="skip"
                )
            )

    # ACTUAL / FORECAST DIVIDER
    if not actual_plot.empty and not forecast_plot.empty:
        last_actual_date = actual_plot["date"].max()
        fig.add_vline(
            x=last_actual_date,
            line_dash="dot",
            annotation_text="Forecast starts",
            annotation_position="top"
        )

    # CHART LAYOUT
    level_name = forecast_level.title()
    if forecast_level == "REGION":
        chart_title = f"Power Demand Forecast — {selected_forecast_region}"
    elif forecast_level == "STATE":
        chart_title = f"Power Demand Forecast — {selected_forecast_state}"
    else:
        chart_title = "Power Demand Forecast — India"

    fig.update_layout(
        title=chart_title,
        xaxis_title="Date",
        yaxis_title="Demand (MU)",
        hovermode="x unified",
        height=650,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        )
    )
    fig.update_xaxes(range=["2017-05-01", "2030-12-31"])

    # DISPLAY CHART
    st.plotly_chart(fig,use_container_width=True)

with tab2:
    st.header("Power Source Dashboard")

    SOURCE_COLUMNS = ["nuclear","wind","solar","hydro","gas","thermal"]
    SOURCE_LABELS = {"nuclear": "Nuclear","wind": "Wind","solar": "Solar","hydro": "Hydro","gas": "Gas","thermal": "Thermal"}
    RENEWABLE_SOURCES = ["wind","solar","hydro"]

    lifecycle_ef = ef_df.set_index("source_key")["lifecycle_ef_gco2eq_kwh"].to_dict()
    operational_ef = ef_df.set_index("source_key")["operational_ef_gco2eq_kwh"].to_dict()

    resolution = st.radio("Time Resolution",["15 Min", "Hourly", "Daily", "Monthly", "Yearly"],horizontal=True,index=0)
    if resolution == "15 Min":
        df = load_minute_data()
    elif resolution == "Hourly":
        df = load_hourly_data()
    elif resolution == "Daily":
        df = load_daily_data()
    elif resolution == "Monthly":
        df = load_monthly_data()
    elif resolution == "Yearly":
        df = load_yearly_data()

    for source in SOURCE_COLUMNS:
        df[f"{source}_lifecycle_emissions"] = df[source].fillna(0) * lifecycle_ef[source]
        df[f"{source}_operational_emissions"] = df[source].fillna(0) * operational_ef[source]

    lifecycle_emission_columns = [f"{source}_lifecycle_emissions" for source in SOURCE_COLUMNS]
    operational_emission_columns = [f"{source}_operational_emissions" for source in SOURCE_COLUMNS]

    df["total_generation_kwh"] = df[SOURCE_COLUMNS].fillna(0).sum(axis=1)
    df["total_lifecycle_emissions_gco2eq"] = df[lifecycle_emission_columns].fillna(0).sum(axis=1)
    df["total_operational_emissions_gco2eq"] = df[operational_emission_columns].fillna(0).sum(axis=1)

    df["renewable_generation_kwh"] = df[RENEWABLE_SOURCES].fillna(0).sum(axis=1)
    df["renewable_share"] = df["renewable_generation_kwh"].div(df["total_generation_kwh"].replace(0, pd.NA)) * 100

    ###########Intensity ############################
    df["lifecycle_emission_intensity"] = df["total_lifecycle_emissions_gco2eq"].div(df["total_generation_kwh"].replace(0, pd.NA))
    df["operational_emission_intensity"] = df["total_operational_emissions_gco2eq"].div(df["total_generation_kwh"].replace(0, pd.NA))

    available_periods = df["generation_time"].dropna().drop_duplicates().sort_values().tolist()

    if not available_periods:
        st.warning(f"No generation data is available for the selected {resolution.lower()} resolution.")
        st.stop()

    selected_period = st.select_slider(
        "Select Time Period",
        options=available_periods,
        value=available_periods[-1],
        format_func=lambda x: x.strftime("%Y-%m-%d %H:%M")
    )
    selected_df = df[df["generation_time"] == selected_period].copy()

    selected_row = selected_df.iloc[0]
    total_generation = selected_row["total_generation_kwh"]
    renewable_share = selected_row["renewable_share"]
    lifecycle_intensity = selected_row["lifecycle_emission_intensity"]
    operational_intensity = selected_row["operational_emission_intensity"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Generation",f"{total_generation/1_000_000:,.2f} MU")
    col2.metric("Lifecycle Intensity",f"{lifecycle_intensity:.1f} gCO₂e/kWh")
    col3.metric("Operational Intensity",f"{operational_intensity:.1f} gCO₂e/kWh")

    st.divider()
    ############################################################
    generation_data = pd.DataFrame({
        "Source": [SOURCE_LABELS[source] for source in SOURCE_COLUMNS],
        "Generation (kWh)": [selected_row[source] for source in SOURCE_COLUMNS]
    })
    generation_data["Generation (kWh)"] = generation_data["Generation (kWh)"].fillna(0)

    ############################################################
    lifecycle_data = pd.DataFrame({
        "Source": [SOURCE_LABELS[source] for source in SOURCE_COLUMNS],
        "Lifecycle Emissions (gCO₂e)": [selected_row[f"{source}_lifecycle_emissions"] for source in SOURCE_COLUMNS]
    })
    lifecycle_data["Lifecycle Emissions (gCO₂e)"] = lifecycle_data["Lifecycle Emissions (gCO₂e)"].fillna(0)

    ############################################################
    operational_data = pd.DataFrame({
        "Source": [SOURCE_LABELS[source] for source in SOURCE_COLUMNS],
        "Operational Emissions (gCO₂e)": [selected_row[f"{source}_operational_emissions"] for source in SOURCE_COLUMNS]
    })
    operational_data["Operational Emissions (gCO₂e)"] = operational_data["Operational Emissions (gCO₂e)"].fillna(0)

    ############################################################
    trend_df = df[["generation_time"] + SOURCE_COLUMNS].copy()
    trend_df = trend_df.melt(id_vars="generation_time",value_vars=SOURCE_COLUMNS,var_name="Source",value_name="Generation (kWh)")
    trend_df["Source"] = trend_df["Source"].map(SOURCE_LABELS)

    ############################################################
    intensity_df = df[["generation_time","lifecycle_emission_intensity","operational_emission_intensity"]].copy()
    intensity_df = intensity_df.rename(
        columns={
            "generation_time":"Time",
            "lifecycle_emission_intensity":"Lifecycle Intensity",
            "operational_emission_intensity":"Operational Intensity"
        }
    )
    intensity_df = intensity_df.melt(
        id_vars="Time",
        value_vars=["Lifecycle Intensity","Operational Intensity"],
        var_name="Metric",
        value_name="gCO₂e/kWh"
    )

    map_df = selected_df[[
        "region_name","geometry","lifecycle_emission_intensity",
        "nuclear","wind","solar","hydro","gas","thermal"
    ]].copy()
    map_df = map_df.dropna(subset=["geometry","lifecycle_emission_intensity"])
    if not map_df.empty:
        features = []
        for _, row in map_df.iterrows():
            geometry = row["geometry"]
            if isinstance(geometry, str):
                geometry = json.loads(geometry)
            features.append({
                "type": "Feature",
                "properties": {
                    "region_name": row["region_name"],
                },
                "geometry": geometry
            })
        geojson = {"type": "FeatureCollection","features": features}

        fig_map = go.Figure(
            go.Choroplethmap(
                geojson=geojson,
                locations=map_df["region_name"],
                z=map_df["lifecycle_emission_intensity"],
                featureidkey="properties.region_name",
                colorscale=[
                    [0.0, "green"],
                    [0.5, "yellow"],
                    [0.75, "brown"],
                    [1.0, "black"]
                ],
                zmin=map_df["lifecycle_emission_intensity"].min(),
                zmax=map_df["lifecycle_emission_intensity"].max(),
                customdata=map_df[[
                    "region_name","lifecycle_emission_intensity",
                    "nuclear","wind","solar","hydro","gas","thermal"
                ]].assign(
                    nuclear=lambda x: x["nuclear"] / 1_000_000,
                    wind=lambda x: x["wind"] / 1_000_000,
                    solar=lambda x: x["solar"] / 1_000_000,
                    hydro=lambda x: x["hydro"] / 1_000_000,
                    gas=lambda x: x["gas"] / 1_000_000,
                    thermal=lambda x: x["thermal"] / 1_000_000
                ).values,

                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Lifecycle Emission Intensity: %{customdata[1]:,.2f} gCO₂e/kWh<br>"
                    "Nuclear: %{customdata[2]:,.2f} MU<br>"
                    "Wind: %{customdata[3]:,.2f} MU<br>"
                    "Solar: %{customdata[4]:,.2f} MU<br>"
                    "Hydro: %{customdata[5]:,.2f} MU<br>"
                    "Gas: %{customdata[6]:,.2f} MU<br>"
                    "Thermal: %{customdata[7]:,.2f} MU"
                    "<extra></extra>"
                ),
                marker_opacity=0.7,
                marker_line_width=1
            )
        )

        fig_map.update_layout(
            map={
                "style": "open-street-map",
                "center": {
                    "lat": 22.5,
                    "lon": 80.0
                },
                "zoom": 3.5
            },
            height=600,
            margin={
                "r": 0,
                "t": 0,
                "l": 0,
                "b": 0
            }
        )
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("Regional geometry is not available for the selected period.")
