# ⚡ India Electricity Grid Analytics

An end-to-end data engineering and analytics platform for India's electricity grid. This project automates daily data extraction from Grid-India, processes power supply and regional source generation data, maintains historical Parquet datasets in GitHub, loads analytical data into Supabase PostgreSQL, generates forecasts using Prophet, and powers an interactive Streamlit dashboard.

## 🏗️ Architecture
<img width="1536" height="1024" alt="ElectricityGrid_Architecture_v2" src="https://github.com/user-attachments/assets/14fb98c6-7f1a-47d9-8bed-2c994e79435d" />

```mermaid
flowchart TD
    A["🗓️ GitHub Actions<p style="font-size: 0.75rem;">Daily trigger · Requests yesterday's report</p>"]
    B["🌐 Amazon API Gateway"]
    C["☁️ AWS Lambda (ap-south-1)<p style="font-size: 0.75rem;">Accesses Grid-India API and downloads the PDF</p>"]
    D["⚡ GRID-INDIA API and PDF CDN<p style="font-size: 0.75rem;">Indian IP required</p>"]
    E["🔄 Extract and Process Report"]
    F["🔌 Power Supply<p style="font-size: 0.75rem;">State-wise Parquet</p>"]
    G["🏭 Source Generation<p style="font-size: 0.75rem;">Region-wise Parquet</p>"]
    H["📈 Prophet Forecasting<p style="font-size: 0.75rem;">Forecasts Power Demand</p>"]
    I["🗄️ Supabase PostgreSQL<p style="font-size: 0.75rem;">ETL workflows · Dimensional model · Three analytical views</p>"]
    J["🗂️ Daily database snapshot stored in GitHub"]
    K["📊 Streamlit Dashboard<p style="font-size: 0.75rem;">Reads prepared data without repeatedly querying Supabase</p>"]

    A --> B
    B --> C
    C <--> D
    C --> B
    B --> A
    A --> E

    E --> F
    E --> G

    F --> H
    G --> I
    H --> I

    I --> J
    J --> K
```

## 📌 Project Overview

The project consists of five automated workflows that handle report extraction, ETL, forecasting, and dashboard data delivery.

### 1. Daily Data Extraction
**Workflow:** [`psp_extract.yml`](.github/workflows/psp_extract.yml)

The extraction workflow runs daily through GitHub Actions and requests the previous day's Power Supply Position (PSP) report.
The workflow calls an Amazon API Gateway endpoint, which invokes an AWS Lambda function hosted in the Asia Pacific (Mumbai) region (`ap-south-1`).

The Lambda function:

1. Authenticates incoming requests using an API key.
2. Queries the Grid-India API for the daily PSP report metadata.
3. Identifies the PDF matching the requested report date.
4. Downloads the PDF from the Grid-India CDN.
5. Returns report metadata and the Base64-encoded PDF to GitHub Actions.

The Lambda function is hosted in Mumbai because the upstream government data source requires access from an Indian IP address.
GitHub Actions then processes the extracted report and generates Parquet files for downstream workflows.

### 2. Permanent Historical Parquet Storage
Processed datasets are maintained in GitHub as permanent historical storage.

**Power Supply Statewise** [View dataset folder](https://github.com/tanmaymelanta/ElectricityGrid/tree/main/Power%20Supply%20Statewise)
- Contains processed state-wise power supply data.

**Source Generation Regionwise** [View dataset folder](https://github.com/tanmaymelanta/ElectricityGrid/tree/main/Source%20Generation%20Regionwise)
- Contains processed regional electricity generation data.

Parquet provides a columnar storage format suitable for analytical workloads and efficient processing.
These historical datasets also provide persisted outputs that can be used by downstream ETL workflows.

### 3. ETL and Database Loading
The extracted Parquet datasets are transformed and loaded into Supabase PostgreSQL through two separate GitHub Actions workflows.

**Power Supply ETL** [`power_supply_etl.yml`](.github/workflows/power_supply_etl.yml)
- Processes state-wise power supply data.
- Applies the required transformations.
- Loads the processed records into the power supply table in Supabase PostgreSQL.

**Source Generation ETL** [`source_generation_etl.yml`](.github/workflows/source_generation_etl.yml)
- Processes regional source generation data.
- Applies the required transformations.
- Loads the processed records into the source generation table in Supabase PostgreSQL.

Separating these workflows keeps the processing logic for the two datasets independent.

### 4. Automated Power Supply Forecasting
**Workflow:** [`power_supply_forecast.yml`](.github/workflows/power_supply_forecast.yml)

The forecasting workflow is triggered after `power_supply_etl.yml` completes.
It uses **Prophet** to forecast power supply / demand metrics and stores the resulting forecasts in a dedicated forecast table in Supabase PostgreSQL.
This integrates forecasting into the automated data pipeline, allowing forecast results to be prepared for downstream visualization without requiring manual execution.

### 5. Dimensional Data Modelling
The Supabase PostgreSQL database uses dimensional data modelling to organize the analytical datasets.

The model accounts for:
- Data grain and the level of detail represented by records.
- State, Region, Date key mapping.
- Separate subject areas for power supply, forecasts, and source generation.

Three database views expose the corresponding datasets:
1. Power Supply View
2. Forecast View
3. Source Generation View

These views provide structured data for downstream consumption and dashboard reporting.

### 6. Cost-Optimized Dashboard Data Delivery

**Workflow:** [`dashboard_extract.yml`](.github/workflows/dashboard_extract.yml)

Repeated database queries from a dashboard can increase database traffic and data-egress costs.
To address this, the dashboard extraction workflow runs once daily and extracts the required datasets from Supabase PostgreSQL. It then stores dashboard-ready output files in GitHub.
The Streamlit application reads these prepared files rather than querying Supabase repeatedly during dashboard interactions.

This architecture:

- Reduces repeated database reads.
- Helps control data-egress costs.
- Separates database processing from dashboard serving.
- Provides a predictable daily refresh cycle.

The trade-off is that dashboard data reflects the most recent successful snapshot rather than necessarily showing real-time database updates.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Data extraction, processing, and transformation |
| GitHub Actions | Workflow scheduling and orchestration |
| AWS Lambda | Serverless extraction from an Indian IP |
| Amazon API Gateway | HTTP endpoint for invoking Lambda |
| Grid-India API / PDF CDN | Source for daily electricity grid reports |
| Parquet | Persistent historical analytical datasets |
| Supabase PostgreSQL | Analytical database and dimensional model |
| Prophet | Time-series forecasting |
| Streamlit | Interactive data visualization dashboard |

## 📂 Repository Structure

```text
ElectricityGrid/
│
├── .github/
│   └── workflows/
│       ├── psp_extract.yml
│       ├── power_supply_etl.yml
│       ├── source_generation_etl.yml
│       ├── power_supply_forecast.yml
│       └── dashboard_extract.yml
│
├── Power Supply Statewise/
│   └── Historical state-wise Parquet datasets
│
├── Source Generation Regionwise/
│   └── Historical regional Parquet datasets
│
├── Data Pipeline Codes/
│   ├── psp_extract.py
│   ├── power_supply_etl.py
│   ├── source_generation_etl.py
│   ├── power_demand_forecast.py
│   └── dashboard_data.py
│
├── streamlit_app/
│   ├── app.py
│   ├── power_supply.parquet
│   ├── forecast.parquet
│   ├── minute.parquet
│   ├── hourly.parquet
│   ├── daily.parquet
│   ├── monthly.parquet
│   ├── yearly.parquet
│   └── emission_factors.csv
│
├── requirements.txt
└── README.md
```

*This is a high-level representation of the repository structure; additional scripts and files may exist.*

## 🚀 Getting Started

### Prerequisites

- Python installed locally.
- Git installed locally.
- Access to the repository.
- Required credentials and configuration if you intend to run database-dependent workflows.

### 1. Clone the Repository

```bash
git clone https://github.com/tanmaymelanta/ElectricityGrid.git
cd ElectricityGrid
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate the environment.

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the Streamlit Dashboard

```bash
streamlit run streamlit_app/app.py
```
Ensure the dashboard's expected data files and paths are available before launching it.

## 🔐 Security Considerations

- Store database credentials, API keys, and GitHub tokens in GitHub Actions Secrets or environment variables.
- Never commit passwords, tokens, or other secrets to the repository.
- Use standard TLS certificate verification for HTTPS requests in the Lambda function.
- Review repository contents before committing large or sensitive datasets.

## 📈 Potential Future Improvements

- Add data quality checks for missing dates, duplicate records, null values, and schema changes.
- Implement retries, error notifications, and pipeline failure alerts.
- Add data freshness and last-successful-run indicators to the dashboard.
- Document fact tables, dimension tables, grain, and join keys with an ER diagram.
- Evaluate forecast accuracy through backtesting and appropriate error metrics.
- Monitor repository growth as historical Parquet datasets accumulate.
- Consider versioning or partitioning historical data to improve maintainability.

## ⚠️ Disclaimer

This project is intended for learning, analytics, and demonstration. Forecasts are estimates, and data should be validated against its original source before being used for operational or policy decisions.
