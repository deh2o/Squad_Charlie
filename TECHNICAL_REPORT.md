# Squad Charlie Digital Oilfield Monitoring & Predictive Maintenance System

## Technical Report

**Project:** Squad Charlie Digital Oilfield Monitoring & Predictive Maintenance System  
**Report type:** Technical / Data Science / Software Engineering Report  
**Status:** Enhanced prototype  
**Date:** 17 September 2026

---

## 1. Executive Summary

Squad Charlie is an end-to-end Digital Oilfield prototype designed to monitor synthetic oil-well operating data, identify abnormal operating conditions, estimate near-term pump-failure risk, explain model predictions, and present the information through a desktop operations-control interface.

The project has evolved from a simple sensor-classification demonstration into a more complete monitoring architecture containing:

- data generation and ingestion;
- row-level data validation and quality reporting;
- SQLite persistence;
- historical-data consolidation;
- time-aware feature engineering;
- a future-oriented `Failure_Next_7D` predictive target;
- chronological machine-learning validation;
- Random Forest failure-risk prediction;
- explainable prediction drivers;
- field-level operational analytics;
- modern multi-view desktop GUI;
- authentication and user roles;
- non-blocking background processing;
- persistent/blinking critical-alert notification bar;
- technical, stakeholder, and field reports;
- email alert capability.

The current implementation is a **prototype**, not a production field-deployment system. The underlying datasets are synthetic and relatively small, and the model therefore demonstrates architecture and workflow rather than validated real-world failure probabilities. The model evaluation is also sensitive to the limited historical sample and the synthetic relationship between generated sensor values and failure labels.

---

## 2. Project Objectives

### 2.1 Primary objective

Provide an integrated software system that can monitor oil-well operating conditions and identify wells requiring increased maintenance attention based on measured operating data and machine-learning risk estimates.

### 2.2 Engineering objectives

The project aims to demonstrate the complete path from raw operational data to an operator-facing decision-support interface:

1. Generate or ingest sensor data.
2. Validate incoming records.
3. Persist historical observations.
4. Engineer time-dependent features.
5. Define a future failure target.
6. Train and evaluate a predictive model using time-aware validation.
7. Generate well-level predictions.
8. Explain important risk signals.
9. Aggregate information at field level.
10. Present the results in a responsive desktop GUI.
11. Generate reports and alerts.
12. Provide authentication and role-aware access.

---

## 3. System Scope

The current prototype monitors the following well variables:

| Variable | Description | Unit / Type |
|---|---|---|
| `Well_ID` | Unique well identifier | Identifier |
| `Date` | Observation date | ISO date |
| `Oil_Rate` | Oil production rate | bbl/day |
| `Water_Cut` | Water fraction of produced fluid | % |
| `Pressure` | Well/process pressure | psi |
| `Temperature` | Operating temperature | °C |
| `Pump_Status` | Recorded pump state | 0 / 1 |

The predictive target introduced during enhancement is:

```text
Failure_Next_7D
```

It represents whether a well has a recorded pump failure during the following seven complete calendar days, subject to the availability of the required future observations.

---

## 4. High-Level Architecture

```text
                     ┌─────────────────────┐
                     │ Synthetic / CSV Data │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Data Validation     │
                     │ validation.py       │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Historical Data     │
                     │ Consolidation       │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ SQLite Database     │
                     │ production_data     │
                     └──────────┬──────────┘
                                │
                ┌───────────────┴────────────────┐
                │                                │
                ▼                                ▼
       ┌─────────────────┐             ┌─────────────────┐
       │ Feature         │             │ Future Target   │
       │ Engineering     │             │ Failure_Next_7D │
       └────────┬────────┘             └────────┬────────┘
                └───────────────┬───────────────┘
                                ▼
                     ┌─────────────────────┐
                     │ Time-Aware ML       │
                     │ Training            │
                     └──────────┬──────────┘
                                ▼
                     ┌─────────────────────┐
                     │ Model Artifact      │
                     │ Random Forest +     │
                     │ metadata            │
                     └──────────┬──────────┘
                                ▼
                     ┌─────────────────────┐
                     │ Prediction Engine   │
                     └──────────┬──────────┘
                                │
                ┌───────────────┼────────────────┐
                ▼               ▼                ▼
          Risk Score      Explainability   Field Analytics
                │               │                │
                └───────────────┼────────────────┘
                                ▼
                    ┌────────────────────────┐
                    │ Modern Control Center  │
                    │ Authentication         │
                    │ Overview / Wells       │
                    │ Predictions / Analytics│
                    │ Reports / Data / System│
                    └────────────┬───────────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
          Alert Bar          Reports          Email Alerts
```

### Architecture principle

The application separates **data acquisition**, **data quality**, **feature preparation**, **modeling**, **prediction**, **explainability**, **analytics**, and **presentation**. This separation makes it possible to improve an individual layer without rewriting the entire application.

---

## 5. Data Acquisition and Data Quality

### 5.1 Synthetic data

The project includes a synthetic-data generator for demonstration and testing. The generator creates well observations with deterministic random behavior so that development runs are reproducible.

The synthetic data deliberately creates a detectable relationship between certain sensor conditions and pump failures. In particular, failure records are associated with degraded production and pressure conditions. This makes the prototype useful for demonstrating the ML pipeline, but it also means model performance should not be interpreted as evidence of real field performance.

### 5.2 Validation layer

`validation.py` provides row-level validation before data reaches the database.

The validation layer checks:

- required column count;
- well-ID format;
- valid ISO dates;
- missing numeric values;
- finite numeric values;
- configured numeric sanity limits;
- valid pump-status values.

The loader also produces an ingestion-quality report containing:

```text
Total rows
Inserted rows
Skipped rows
Rejected rows
Malformed rows
Validation errors
Quality score
```

This establishes a formal boundary between raw source data and trusted application data.

### 5.3 Idempotent loading

Production observations are uniquely identified by:

```text
(Well_ID, Date)
```

This prevents repeated ingestion from creating duplicate observations.

---

## 6. Historical Data Consolidation

The enhanced pipeline supports multiple CSV batches instead of treating a single CSV as the complete history.

Historical batches are validated and consolidated before modeling. Duplicate `Well_ID + Date` observations are resolved rather than blindly inserted.

The consolidation layer is also calendar-aware. A gap of several days or months is not treated as if it were a continuous sensor sequence.

This is particularly important for lag and rolling features.

---

## 7. Feature Engineering

A dedicated `feature_engineering.py` module prepares historical features for the predictive model.

The engineered feature set includes recent changes, rolling statistics, and trend indicators such as:

```text
Oil_Rate_Change_1D
Oil_Rate_Change_3D
Oil_Rate_Change_7D
Pressure_Change_1D
Pressure_Change_3D
Pressure_Change_7D
Oil_Rate_7D_Average
Pressure_7D_Average
Temperature_7D_Average
Oil_Rate_7D_Std
Pressure_7D_Std
Oil_Rate_Decline_Rate
Pressure_Decline_Rate
Water_Cut_Trend
```

### Time-awareness

Features are calculated separately for each well:

```text
WELL-01 history → WELL-01 features
WELL-02 history → WELL-02 features
...
```

A reading from one well cannot become the previous observation for another well.

Feature calculations use information available at or before the prediction timestamp. Future observations are not used to construct current features.

---

## 8. Predictive Target Engineering

The original prototype classified the same-day `Pump_Status`. That is closer to failure detection than predictive maintenance.

The enhanced pipeline introduces:

```text
Failure_Next_7D
```

The target asks whether a failure occurs during the following seven calendar days.

### Incomplete future windows

Rows near the end of an available historical period may not have seven subsequent observations. These rows are not incorrectly labeled as normal. They are treated as unavailable for the future-horizon training target.

This prevents the model from learning false negative examples created solely by missing future data.

---

## 9. Machine Learning Methodology

### 9.1 Algorithm

The baseline model is a `RandomForestClassifier` from scikit-learn.

The enhanced configuration uses a larger ensemble and class balancing to handle the relatively infrequent failure class:

```python
RandomForestClassifier(
    n_estimators=300,
    max_depth=8,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)
```

Random Forest was selected as a strong baseline because it:

- handles non-linear relationships;
- does not require feature scaling;
- works well with numeric sensor features;
- provides native feature-importance values;
- is straightforward to serialize and deploy in a desktop application.

### 9.2 Time-aware evaluation

The enhanced training process avoids randomly shuffling historical observations for the primary train/test split.

The conceptual structure is:

```text
Earlier observations                     Later observations
───────────────────────────────────────│────────────────────
              TRAINING                  │       TEST
                                        │
                                  time cutoff
```

This is more representative of deployment because the model is expected to predict future conditions from past information.

### 9.3 Model artifact

The model file now stores both the estimator and important metadata, including:

- trained model;
- feature list;
- target name;
- prediction horizon;
- model version;
- training timestamp;
- training/test row counts;
- time cutoff;
- evaluation metrics;
- feature baselines.

This avoids the previous problem where downstream code assumed the serialized file was always a raw scikit-learn estimator.

---

## 10. Explainable Predictions

The explainability layer compares the current feature state against model reference baselines and estimates how individual features affect the predicted risk.

The application can therefore expose information such as:

```text
7-Day Failure Risk: 82%
Risk Level: CRITICAL

Key Risk Signals
────────────────────────
Oil-rate decline       ↑ risk
Pressure decline       ↑ risk
Water-cut trend        ↑ risk
Pressure volatility    ↑ risk
Temperature trend      ↓ risk
```

These are model-derived signals, not causal engineering conclusions. Operators should use them as decision-support information and verify conditions using appropriate field procedures.

---

## 11. Field-Level Analytics

`field_analytics.py` aggregates individual observations and predictions into field-level indicators.

The analytics layer distinguishes between:

### Observed operational indicators

- number of monitored wells;
- production volume/rate;
- average water cut;
- average pressure;
- temperature statistics;
- historical failure count/rate;
- uptime.

### Predictive indicators

- average 7-day failure risk;
- Normal/Warning/Critical distribution;
- wells requiring increased model-based attention;
- model-risk summaries.

The distinction is intentional: **a predicted critical risk is not the same thing as a confirmed equipment failure.**

---

## 12. Modern Desktop Control Center

The GUI was redesigned from a single legacy dashboard into a multi-view operations interface.

### Main views

```text
Overview
Wells
Predictions
Analytics
Reports
Data
System
```

### Overview

The Overview workspace provides the field's primary operating picture:

- field KPI cards;
- production monitoring;
- risk distribution;
- well monitoring;
- quick actions;
- selected-well intelligence.

The Well Monitoring area starts on the **Overview** tab by default.

### Wells

The Wells workspace provides:

- searchable wells;
- immediate well selection;
- current operating measurements;
- model risk;
- risk classification;
- explainability drivers;
- selected-well charts.

The UI uses stale-result protection so that a slower background result for an old selection cannot overwrite the currently selected well.

### Predictions

The Predictions workspace provides a field-wide view of model risk and individual well predictions.

### Analytics

The Analytics workspace exposes exploratory and model-analysis views including feature importance, failure precursors, decline behavior, health indicators, forecast views, and production-loss analysis where available.

### Reports

Reports include technical, stakeholder, and field-overview outputs. **Field Overview** is the first/default report tab and is loaded automatically when the Reports workspace is opened.

### Data

The Data workspace supports controlled data generation, validation, ingestion, database statistics, and export/administrative operations according to user permissions.

### System

System functions include database status, logging, email configuration/testing, and session controls.

---

## 13. Authentication and Authorization

The application now requires authentication before access to the main dashboard.

### Login flow

```text
Application start
       ↓
Authentication screen
       ↓
Create first administrator (first run)
       ↓
Login
       ↓
Authenticated session
       ↓
Control Center
```

### Password security

Passwords are not stored as plaintext. The authentication layer uses salted PBKDF2-HMAC-SHA256 password hashing and constant-time verification.

### Roles

The current role model supports:

```text
ADMIN
OPERATOR
VIEWER
```

Role-aware access is used to restrict sensitive operations. For example, destructive database operations should not be available to read-only users.

Authentication events can also be logged for audit visibility.

---

## 14. Responsive Background Processing

A major GUI reliability improvement is the separation of expensive work from the Tkinter main event loop.

Operations such as:

- field-wide predictions;
- well intelligence loading;
- database-heavy analytics;
- report generation;
- SMTP/email operations;
- periodic monitoring

are performed in background workers where appropriate.

The main UI thread remains responsible for rendering and user interaction.

Conceptually:

```text
                    USER ACTION
                         │
                         ▼
                   UI THREAD
                  /          \
                 /            \
        immediate UI       background task
           update                │
              │                  ▼
              │             ML / DB / SMTP
              │                  │
              └──────────┬───────┘
                         ▼
                    UI UPDATE
```

This prevents slow prediction, report, or email operations from freezing the interface.

---

## 15. Critical Alert System

The enhanced GUI uses a persistent notification bar at the top of the control center for critical model alerts.

Example:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ ⚠ CRITICAL • WELL-05 | 7-day failure risk 93.4%   VIEW WELL  ACKNOWLEDGE │
└──────────────────────────────────────────────────────────────────────┘
```

### Alert behavior

When a well enters the configured critical-risk state:

1. A critical alert is created.
2. The notification bar becomes visible.
3. The bar blinks continuously.
4. The operator can open the affected well.
5. The operator can acknowledge the alert.
6. The alert remains logically distinct from the underlying prediction.
7. If the risk later returns to normal and becomes critical again, a new alert can be generated.

The alert system is designed to avoid repeatedly interrupting the operator with modal popup windows.

---

## 16. Reports and Email Alerts

The reporting layer generates:

- technical reports;
- stakeholder summaries;
- field-overview reports.

Email notifications can be sent when a configured critical condition is reached.

When email credentials are not configured, the application can operate in a dry-run mode for demonstrations, allowing the workflow to be tested without sending external messages.

Production deployments should store credentials using a managed secrets mechanism rather than plain-text configuration files.

---

## 17. Testing and Quality Assurance

The project has been incrementally tested after each major enhancement.

The test coverage includes:

- database setup;
- validation of valid and invalid rows;
- malformed CSV handling;
- ingestion idempotency;
- feature engineering;
- cross-well isolation;
- future target generation;
- time-aware training preparation;
- explainability;
- field analytics;
- authentication and password handling.

The latest development cycle reported all automated tests passing at the time of the enhancements.

The project should continue to add integration tests around the GUI, alert lifecycle, role permissions, and end-to-end training/inference compatibility.

---

## 18. Known Limitations

### Data limitations

- Current operational data is synthetic.
- Historical volume is small compared with a real field deployment.
- Failure labels are generated rather than independently verified from maintenance records.
- Sensor quality, calibration, downtime causes, and maintenance interventions are not yet modeled in sufficient detail.

### ML limitations

- A Random Forest baseline is not sufficient evidence for production deployment.
- Probability calibration has not been fully validated.
- The model should be compared with simpler baselines and alternative algorithms.
- Real field data may exhibit concept drift and well-specific behavior not represented in the synthetic data.
- The alert threshold should ultimately be selected using the business cost of missed failures versus unnecessary interventions.

### Software limitations

- The current application is a desktop prototype rather than a distributed production platform.
- Durable alert history and escalation workflows need further development.
- Scheduled model retraining and drift monitoring are not yet a full production service.
- Model/data schema versioning should be strengthened.
- Secrets should move to managed secret storage for production use.
- A service/API layer would be appropriate if multiple users or remote operations are required.

---

## 19. Recommended Future Roadmap

### Phase 1 — Data and ML reliability

1. Replace synthetic data with validated historical sensor and maintenance data.
2. Add independent failure/maintenance labels.
3. Increase the historical observation window.
4. Add chronological validation with an untouched future test period.
5. Add grouped validation when testing generalization across wells.
6. Calibrate predicted probabilities.
7. Establish threshold-selection criteria based on operational cost.

### Phase 2 — Industrial analytics

1. Add sensor-quality flags and anomaly detection.
2. Add well-specific baselines.
3. Add production-loss estimation.
4. Add maintenance-history integration.
5. Add equipment hierarchy and asset relationships.
6. Add model drift and data drift monitoring.

### Phase 3 — Production platform

1. Separate the inference engine from the desktop GUI.
2. Expose predictions through an API.
3. Add scheduled ingestion and scoring.
4. Introduce durable alert/event storage.
5. Add escalation and acknowledgement history.
6. Integrate enterprise authentication/SSO where required.
7. Use managed secrets.
8. Containerize the service layer.
9. Add CI/CD and automated model validation.
10. Introduce centralized observability.

---

## 20. Conclusion

Squad Charlie now represents a coherent Digital Oilfield predictive-maintenance prototype rather than only a basic machine-learning demonstration.

The most important architectural improvements are the move from same-day failure classification to a future-oriented seven-day target, time-aware feature preparation and model evaluation, explainable risk outputs, field-level analytics, authentication, background processing, and persistent critical-alert handling.

The system is suitable for demonstrating an end-to-end engineering workflow across **Python software development, data engineering, machine learning, analytics, reporting, automation, and operational UI design**.

It should not yet be treated as a production predictive-maintenance system. The next major credibility step is to replace the synthetic data and generated failure labels with independent field data and maintenance outcomes, then validate the system against a properly separated future test period.
