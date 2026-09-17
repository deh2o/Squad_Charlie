# Squad Charlie — Digital Oilfield Monitoring & Predictive Maintenance System

Squad Charlie is an end-to-end **Digital Oilfield monitoring and predictive-maintenance prototype** built with Python. It combines data engineering, data validation, machine learning, explainable predictions, field analytics, reporting, automated alerts, authentication, and a modern desktop operations-control interface.

> **Prototype notice:** The current project uses synthetic operational data. Model predictions are intended for demonstration and decision support, not as validated real-world equipment-failure probabilities.

---

## Features

- Synthetic oil-well sensor-data generation
- CSV ingestion and validation
- SQLite historical data store
- Idempotent data loading
- Historical data consolidation
- Time-aware feature engineering
- Seven-day future failure target: `Failure_Next_7D`
- Random Forest predictive-maintenance model
- Chronological train/test evaluation
- Model metadata and feature-schema persistence
- Explainable prediction drivers
- Field-level production and risk analytics
- Modern multi-view desktop GUI
- User login/authentication
- `ADMIN`, `OPERATOR`, and `VIEWER` roles
- Responsive background processing
- Searchable well monitoring
- Predictive risk dashboard
- Blinking critical-alert notification bar
- Alert acknowledgement and well drill-down
- Technical, stakeholder, and field reports
- Email alert support with dry-run mode
- Automated tests

---

## Architecture

```text
Raw / Synthetic Data
        │
        ▼
Data Validation
(validation.py)
        │
        ▼
Historical Consolidation
        │
        ▼
SQLite Database
(data/oilfield.db)
        │
        ├──────────────────────┐
        ▼                      ▼
Feature Engineering      Future Target
(feature_engineering.py) (predictive_target.py)
        │                      │
        └───────────┬──────────┘
                    ▼
             Model Training
            (train_model.py)
                    │
                    ▼
          Random Forest Artifact
       (models/pump_failure_model.pkl)
                    │
                    ▼
              Prediction Engine
                (predict.py)
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
     Explainability Field     Reports
     (risk drivers) Analytics
          │         │          │
          └─────────┼──────────┘
                    ▼
          Modern Control Center
             (modern_app.py)
                    │
      ┌─────────────┼────────────────────┐
      ▼             ▼                    ▼
 Authentication   Dashboard          Alert System
      │             │                    │
      ▼             ▼                    ▼
 Roles         Overview/Wells       Critical bar
              Predictions/EDA       Email alerts
              Reports/Data/System
```

### Architecture layers

| Layer | Responsibility |
|---|---|
| Data generation | Creates deterministic synthetic sensor data for development/demo use |
| Validation | Rejects malformed, invalid, missing, or out-of-range records |
| Storage | Persists historical observations in SQLite |
| Feature engineering | Creates lag, rolling, volatility, and trend features |
| Target engineering | Creates the future seven-day failure target |
| ML | Trains and evaluates the Random Forest classifier |
| Prediction | Produces failure probability and risk level |
| Explainability | Identifies important current risk signals |
| Field analytics | Aggregates well-level data into field KPIs |
| GUI | Provides the operator-facing control center |
| Authentication | Controls access and user roles |
| Alerts | Displays critical conditions and optionally sends email |
| Reports | Produces technical and stakeholder summaries |

---

## Project Structure

```text
squad_charlie/
│
├── modern_app.py              # Main modern GUI entry point
├── app.py                     # Legacy/original GUI
│
├── config.py                  # Configuration and paths
├── auth.py                    # Authentication/session logic
├── db_setup.py                # SQLite database initialization
├── data_loader.py             # Database/data access helpers
├── validation.py              # CSV/row validation
├── load_csv.py                # CSV ingestion
├── generate_data.py            # Synthetic sensor-data generator
│
├── feature_engineering.py     # Historical ML feature generation
├── predictive_target.py       # Failure_Next_7D target creation
├── train_model.py             # Model training/evaluation
├── predict.py                 # Well failure-risk inference
├── explainability.py           # Prediction explanation
├── field_analytics.py          # Field/well KPIs
│
├── charts.py                  # Charts and visualizations
├── eda.py                     # Exploratory/model-analysis views
├── reports.py                 # Technical/stakeholder/field reports
├── emailer.py                 # SMTP email alerts
├── logger.py                  # Application logging
│
├── models/
│   └── pump_failure_model.pkl # Generated model artifact
│
├── data/
│   └── oilfield.db            # Generated SQLite database
│
├── raw/                       # Generated/imported CSV batches
│
├── tests/                     # Automated tests
│
├── .env.example               # Environment-variable template
├── Requirements.txt           # Python dependencies
└── README.md
```

---

# Setup Instructions

## 1. Requirements

Recommended environment:

- Python 3.10+
- Windows, Linux, or macOS
- PyCharm, VS Code, or another Python IDE

The application uses Tkinter/CustomTkinter for the desktop interface and scikit-learn for machine learning.

---

## 2. Clone or extract the project

Open a terminal in the project directory:

```bash
cd squad_charlie
```

---

## 3. Create a virtual environment

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use:

```powershell
.\.venv\Scripts\python.exe -m pip install -r Requirements.txt
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 4. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r Requirements.txt
```

For Linux systems where Tkinter is not installed:

```bash
sudo apt install python3-tk
```

---

## 5. Configure email (optional)

Copy the environment template:

```bash
copy .env.example .env
```

On Linux/macOS:

```bash
cp .env.example .env
```

Email is optional. Without valid SMTP credentials, the application can use dry-run behavior for demonstrations.

For Gmail, use an **App Password** rather than your normal Gmail password when the account/security configuration requires it.

Do not commit `.env` to Git.

---

# First Run

The recommended application entry point is:

```bash
python modern_app.py
```

The application should start with the authentication interface.

### First login

On a new installation where no users exist:

```text
Application
    ↓
Create Administrator
    ↓
Create username/password
    ↓
Login
    ↓
Modern Control Center
```

After the first administrator has been created, subsequent launches show the normal login screen.

---

# Data Pipeline

The normal development workflow is:

```text
Generate / import data
        ↓
Validate
        ↓
Load into SQLite
        ↓
Build predictive target/features
        ↓
Train model
        ↓
Run predictions
        ↓
Launch dashboard
```

### 1. Initialize the database

```bash
python db_setup.py
```

### 2. Generate synthetic data

```bash
python generate_data.py
```

This creates synthetic well readings under the configured raw-data location.

### 3. Load CSV data

```bash
python load_csv.py
```

The loader validates records before inserting them and avoids duplicate `Well_ID + Date` records.

If using a specific CSV batch, use the loader's supported path argument/configuration rather than assuming that every generated batch is the default CSV.

### 4. Train the model

```bash
python train_model.py
```

The training pipeline:

1. loads historical observations;
2. prepares the future `Failure_Next_7D` target;
3. creates historical features;
4. removes rows without a complete future target/window;
5. performs a chronological train/test split;
6. trains the Random Forest;
7. evaluates the test period;
8. saves the model and metadata.

### 5. Run predictions manually (optional)

```bash
python predict.py
```

The dashboard normally calls the prediction layer automatically.

---

# Launch the GUI

Use:

```bash
python modern_app.py
```

Do **not** normally start the application with `app.py`; that is the legacy GUI.

The modern application flow is:

```text
Login
  ↓
Overview
  ├── Wells
  ├── Predictions
  ├── Analytics
  ├── Reports
  ├── Data
  └── System
```

---

# Modern Dashboard

## Overview

The Overview workspace provides a field-level control-room view containing:

- production KPIs;
- field uptime;
- historical failure indicators;
- model-risk distribution;
- well monitoring;
- selected-well intelligence;
- critical alerts.

The **Overview** tab under Well Monitoring is selected first and displayed by default.

## Wells

The Wells workspace supports:

- searching wells;
- selecting a well;
- immediate selected-well updates;
- sensor metrics;
- 7-day failure risk;
- risk level;
- explainability drivers;
- selected-well charts.

## Predictions

Provides a field-wide view of model-generated seven-day failure risk.

Risk levels are configuration-driven and should not be interpreted as confirmed equipment states.

## Analytics

Provides analytical views such as:

- feature importance;
- failure precursors;
- decline behavior;
- health indicators;
- forecasting views;
- production-loss analysis.

## Reports

The Reports workspace contains:

- Field Overview;
- Technical Report;
- Stakeholder Report.

Field Overview is loaded by default.

## Data

Used for controlled data generation, validation, ingestion, database inspection, and data administration.

## System

Contains system health, logs, email testing, and session controls.

---

# Critical Alert System

Critical model alerts are displayed in a persistent notification bar at the top of the dashboard.

```text
⚠ CRITICAL • WELL-05 | 7-day failure risk 93.4%
                         [VIEW WELL] [ACKNOWLEDGE]
```

When an active critical alert exists:

- the bar appears automatically;
- the notification blinks;
- the affected well can be opened directly;
- the operator can acknowledge the alert;
- background monitoring continues without freezing the GUI.

The application is designed to avoid repeatedly showing disruptive modal popups for the same active condition.

---

# GUI Responsiveness

Expensive operations are moved away from the Tkinter main event loop where appropriate.

Background processing is used for operations such as:

- field-wide prediction scans;
- well intelligence retrieval;
- report generation;
- database-heavy work;
- SMTP/email operations;
- periodic monitoring.

This allows the interface to remain interactive while work is being performed.

---

# Authentication and Roles

The application requires login before the dashboard becomes accessible.

Supported roles:

| Role | Typical access |
|---|---|
| `ADMIN` | Full administration and configuration |
| `OPERATOR` | Monitoring, diagnostics, reports, operational actions |
| `VIEWER` | Read-only monitoring and analytics |

Sensitive/destructive operations should remain restricted to authorized roles.

Passwords are stored using salted password hashing rather than plaintext storage.

---

# Testing

Run the automated test suite with:

```bash
python -m pytest -q
```

For more detail:

```bash
python -m pytest -v
```

Before committing changes, also check syntax:

```bash
python -m py_compile modern_app.py
```

For the full project, compile/check the modified modules as required.

---

# Model Interpretation

The model predicts a **future failure-risk signal**, not a guaranteed failure.

For example:

```text
WELL-05
7-Day Failure Risk: 82%
Level: CRITICAL
```

means the model has estimated elevated risk according to the configured model and threshold. It does not mean that the pump is confirmed to fail.

The explainability panel shows signals that contributed to the model output, but those signals should not automatically be interpreted as physical causation.

---

# Development Notes

## Generated files

The following are normally generated locally and should generally not be committed unless intentionally versioned as demo fixtures:

```text
data/oilfield.db
raw/*.csv
models/*.pkl
logs/*
.env
```

Add them to `.gitignore` where appropriate.

## Re-training

Retrain the model after significant changes to:

- historical data;
- feature engineering;
- target definition;
- model configuration.

Then verify that the prediction and explainability modules are compatible with the saved model artifact.

---

# Known Limitations

This project is an engineering prototype. Important limitations include:

- synthetic rather than field-validated data;
- limited historical sample size;
- synthetic failure labels;
- no confirmed maintenance/work-order integration;
- no production-grade model monitoring;
- no enterprise SSO integration;
- no distributed API/inference service;
- durable alert history and escalation are still candidates for further development;
- model probabilities require calibration before operational use.

---

# Recommended Next Development Stages

1. Integrate real or high-fidelity historical production and maintenance data.
2. Add durable alert history and escalation workflows.
3. Add sensor anomaly/data-drift detection.
4. Add model calibration and threshold optimization.
5. Add grouped validation for new-well generalization.
6. Add scheduled ingestion and scoring.
7. Add API/service separation from the desktop GUI.
8. Add CI/CD and automated model validation.
9. Containerize the service layer.
10. Add centralized logging and monitoring.

---

# Project Value

Squad Charlie demonstrates an integrated engineering workflow across:

- **Python software development**
- **Data engineering**
- **Data quality and validation**
- **SQL / SQLite**
- **Machine learning**
- **Time-series feature engineering**
- **Predictive maintenance**
- **Explainable AI**
- **Data analytics**
- **Desktop GUI development**
- **Authentication and authorization**
- **Automation and alerting**
- **Technical reporting**

The project is intended to demonstrate how these disciplines can be combined into an operational Digital Oilfield decision-support application.
