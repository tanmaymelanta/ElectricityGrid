import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text

from db import get_engine


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="India Power Supply Dashboard",
    page_icon="⚡",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("⚡ India Power Supply Dashboard")

st.caption(
    "Source: Statewise Power Supply Data"
)


# ============================================================
# DATABASE
# ============================================================

engine = get_engine()


# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data(ttl=300)
def load_data():

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
    """

    return pd.read_sql(
        query,
        engine
    )


df = load_data()


# ============================================================
# BASIC CLEANUP
# ============================================================

df["report_date"] = pd.to_datetime(
    df["report_date"]
)


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.header("Filters")


# Date

min_date = df["report_date"].min().date()
max_date = df["report_date"].max().date()

date_range = st.sidebar.date_input(
    "Report Date",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)


# Region

regions = sorted(
    df["region_name"]
    .dropna()
    .unique()
)

selected_regions = st.sidebar.multiselect(
    "Region",
    regions,
    default=regions
)


# State

states = sorted(
    df["state_name"]
    .dropna()
    .unique()
)

selected_states = st.sidebar.multiselect(
    "State",
    states
)


# ============================================================
# APPLY FILTERS
# ============================================================

filtered_df = df.copy()


if len(date_range) == 2:

    start_date, end_date = date_range

    filtered_df = filtered_df[
        (
            filtered_df["report_date"].dt.date
            >= start_date
        )
        &
        (
            filtered_df["report_date"].dt.date
            <= end_date
        )
    ]


if selected_regions:

    filtered_df = filtered_df[
        filtered_df["region_name"].isin(
            selected_regions
        )
    ]


if selected_states:

    filtered_df = filtered_df[
        filtered_df["state_name"].isin(
            selected_states
        )
    ]


# ============================================================
# KPI SECTION
# ============================================================

col1, col2, col3, col4 = st.columns(4)


col1.metric(
    "Energy Met",
    f"{filtered_df['energy_met_mu'].sum():,.1f} MU"
)


col2.metric(
    "Max Demand",
    f"{filtered_df['max_demand_met_mw'].max():,.0f} MW"
)


col3.metric(
    "Energy Shortage",
    f"{filtered_df['energy_shortage_mu'].sum():,.1f} MU"
)


col4.metric(
    "States",
    filtered_df["state_name"].nunique()
)


# ============================================================
# ENERGY MET OVER TIME
# ============================================================

st.subheader("Energy Met Over Time")


daily_energy = (
    filtered_df
    .groupby("report_date", as_index=False)
    ["energy_met_mu"]
    .sum()
)


fig = px.line(
    daily_energy,
    x="report_date",
    y="energy_met_mu",
    title="Daily Energy Met"
)


fig.update_layout(
    xaxis_title="Date",
    yaxis_title="Energy Met (MU)"
)


st.plotly_chart(
    fig,
    use_container_width=True
)


# ============================================================
# REGION COMPARISON
# ============================================================

st.subheader("Energy Met by Region")


region_df = (
    filtered_df
    .groupby("region_name", as_index=False)
    ["energy_met_mu"]
    .sum()
    .sort_values(
        "energy_met_mu",
        ascending=False
    )
)


fig = px.bar(
    region_df,
    x="region_name",
    y="energy_met_mu",
    title="Energy Met by Region"
)


fig.update_layout(
    xaxis_title="Region",
    yaxis_title="Energy Met (MU)"
)


st.plotly_chart(
    fig,
    use_container_width=True
)


# ============================================================
# STATE TABLE
# ============================================================

st.subheader("Statewise Data")


state_summary = (
    filtered_df
    .groupby(
        [
            "state_name",
            "region_name"
        ],
        as_index=False
    )
    .agg(
        {
            "energy_met_mu": "sum",
            "max_demand_met_mw": "max",
            "energy_shortage_mu": "sum",
            "drawal_schedule_mu": "sum",
            "od_ud_mu": "sum"
        }
    )
)


st.dataframe(
    state_summary,
    use_container_width=True,
    hide_index=True
)
