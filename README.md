# ⚡ India Electricity Grid Analytics

An end-to-end data engineering and analytics project for exploring India's electricity grid. The project collects and processes grid-related data, organizes it into datasets for analysis, and presents key insights through a Streamlit dashboard.

## Overview

ElectricityGrid brings together data pipelines and an interactive dashboard focused on:

- **State-wise power supply** — explore electricity supply information by state.
- **Regional source generation** — inspect electricity generation by source and region.
- **Forecasting** — includes forecasting-related dependencies and pipeline components.
- **Emissions analysis** — use source-specific emission factors to support estimated emissions analysis.
- **Automated data workflows** — use Python scripts and GitHub Actions to support repeatable data processing.

> **Note:** Data availability, forecast coverage, refresh frequency, and dashboard functionality depend on the current implementation and upstream data sources.

## Project structure

```text
ElectricityGrid/
├── .github/workflows/          # GitHub Actions workflows
├── Data Pipeline Codes/        # Data processing / pipeline scripts
├── Power Supply Statewise/     # State-wise power supply data or outputs
├── Source Generation Regionwise/ # Regional generation data or outputs
├── streamlit_app/              # Streamlit dashboard application
├── Scraper.py                  # Data collection / scraping entry point
├── emission_factors.csv        # Emission factors used for analysis
├── github_upload.py            # GitHub upload helper
└── requirements.txt            # Python dependencies
```

## Technology stack

- **Python** for data collection and transformation
- **Pandas** and **PyArrow** for tabular and Parquet data processing
- **SQLAlchemy** and **PostgreSQL** driver (`psycopg`) for database interactions
- **Streamlit** for the interactive dashboard
- **Prophet** for forecasting-related functionality
- **Requests** for HTTP requests
- **GitHub Actions** for workflow automation

The exact role of each dependency may vary by script; see `requirements.txt` and the individual modules for implementation details.

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/tanmaymelanta/ElectricityGrid.git
cd ElectricityGrid
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the dashboard

The Streamlit application is located in `streamlit_app/`. Find the main Streamlit entry-point file in that directory and run it, for example:

```bash
streamlit run streamlit_app/<your_app_file>.py
```

Replace `<your_app_file>.py` with the actual application filename.

### 5. Configure data pipelines

Review the scripts in `Data Pipeline Codes/`, `Scraper.py`, and `github_upload.py` before running pipeline jobs. Configure any required database credentials, API tokens, or other settings through environment variables or a local `.env` file as appropriate to the code.

**Security:** Never commit database passwords, API keys, GitHub tokens, or other secrets to the repository. Use GitHub Actions Secrets for credentials needed by automated workflows.

## Data and interpretation

- Check the source and timestamp of each dataset before using it for analysis.
- Treat forecasts as estimates, not guaranteed future outcomes.
- Emissions figures depend on the emission factors and calculation assumptions used by the project.
- Confirm units, time resolution, missing values, and geographic coverage in the source data before comparing results.

## Roadmap ideas

Potential future improvements include:

- Documenting each pipeline's source, transformations, schedule, and output schema.
- Adding data-quality checks for missing, duplicate, and out-of-range records.
- Showing dataset freshness and pipeline status in the dashboard.
- Documenting forecasting methodology and evaluation metrics.
- Adding screenshots and a deployed dashboard link.

## Contributing

Suggestions, bug reports, and improvements are welcome. Open an issue or submit a pull request with a clear description of the change.

## Disclaimer

This project is intended for learning, analysis, and demonstration. Validate data sources, assumptions, and outputs before using results for operational or policy decisions.
