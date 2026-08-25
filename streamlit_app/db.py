import streamlit as st
from sqlalchemy import create_engine


@st.cache_resource
def get_engine():

    database_url = st.secrets["DATABASE_URL"]

    return create_engine(
        database_url,
        pool_pre_ping=True
    )
