# Squad Charlie: Data Science and Machine Learning Technical Report

**Project:** Digital Oilfield Monitoring and Predictive Maintenance System  
**Report date:** 2026-09-15  
**Repository:** `deh2o/Squad_Charlie`

## 1. Executive summary

Squad Charlie is an end-to-end prototype for monitoring oil wells and estimating
the probability of pump failure. The system generates synthetic sensor readings,
loads them into SQLite, trains a scikit-learn `RandomForestClassifier`, scores
the latest reading for each well, and presents the result through a Tkinter
dashboard with charts, technical reports, and email alerts.

The implementation demonstrates a coherent proof of concept and a reproducible
demo pipeline. It is not yet a production-grade predictive-maintenance model:
the training data are simulated, the available history is small, the evaluation
is a single random hold-out split, and the model is not accompanied by a
versioned experiment record, calibration analysis, or monitoring process.
Consequently, the reported risk should be treated as a prototype decision
signal, not as a validated probability of real-world failure.

## 2. Methodology overview

The project follows the main data-science lifecycle:

1. Define the operational problem and prediction target.
2. Acquire and persist source data.
3. Explore and validate the data.
4. Prepare features and labels.
5. Split data for model development and evaluation.
6. Train a supervised classification model.
7. Evaluate discrimination and classification behavior.
8. Deploy inference into an operational workflow.
9. Communicate results and trigger actions.
10. Monitor, retrain, and improve the system.

Steps 1-9 are represented in code to varying degrees. Step 10 is currently a
recommendation rather than an implemented capability.

## 3. Problem definition

### Business objective

Identify wells whose current operating conditions indicate elevated pump-failure
risk, so that engineers can inspect or schedule maintenance before an
unplanned production interruption.

### Analytical task

This is a binary supervised classification problem:

- **Target:** `Pump_Status`
- **Class 0:** normal operation
- **Class 1:** pump failure
- **Output:** `predict_proba(...)[0, 1]`, interpreted by the application as a
  failure-risk score in the range 0-1

### Decision policy

`predict.py` maps the score to operational tiers:

- **NORMAL:** below 0.50
- **WARNING:** 0.50 to below 0.75
- **CRITICAL:** at least 0.75

A CRITICAL score initiates an email alert from the dashboard. These thresholds
are configuration values, not thresholds selected from a documented cost-benefit
or precision-recall analysis.

## 4. Data acquisition and storage

### Source and generation

`generate_data.py` creates a deterministic synthetic dataset using
`random.seed(42)`. The configured demo contains:

- 5 wells (`WELL-01` to `WELL-05`)
- 30 consecutive days per well
- 150 intended readings in total
- an approximately 15% failure rate

Failure rows are deliberately given a simple physical signature: lower pressure
and lower oil rate. This makes the learning task meaningful for a demonstration,
but also creates a strong synthetic relationship that may overstate performance
relative to field data.

### Schema

The seven stored columns are:

| Field | Meaning | Role |
|---|---|---|
| `Well_ID` | Well identifier | Grouping/entity key |
| `Date` | ISO calendar date | Time/order field |
| `Oil_Rate` | Barrels per day | Predictor |
| `Water_Cut` | Water percentage | Predictor |
| `Pressure` | Pressure in psi | Predictor |
| `Temperature` | Temperature in degrees Celsius | Predictor |
| `Pump_Status` | 0 normal, 1 failure | Label |

SQLite stores the data in `production_data`. A unique constraint/index on
`(Well_ID, Date)` makes CSV loading idempotent, and parameterized SQL is used
for well-level queries.

### Data lineage

The documented pipeline is:

```text
generate_data.py -> CSV -> load_csv.py -> SQLite -> train_model.py
                                             |
                                             +-> predict.py -> app.py/reports.py/emailer.py
```

The default generator mode writes a uniquely named file under `raw/`, whereas
the documented `load_csv.py` default reads `data/production_data.csv`. This is
an operational inconsistency: users must explicitly point the loader at the
generated raw file or generate with the non-raw option.

## 5. Data understanding and exploratory analysis

The project provides descriptive analysis at report-generation time:

- `reports.technical_report()` calculates count, mean, standard deviation,
  quartiles, minimum, and maximum for the four sensor variables.
- It also reports failure days, failure rate, mean pressure, and mean oil rate.
- `charts.py` visualizes each sensor over time and marks recorded failure days.
- `reports.field_summary()` aggregates total oil, failure count, and current
  model risk for each well.

This is useful for a demo and for human review, but a formal EDA artifact is
not committed. In particular, the project does not currently record:

- distributions and outlier decisions;
- feature correlation or leakage analysis;
- per-well and per-period class balance;
- missing-value and invalid-range counts;
- train/test distribution comparisons;
- plots or tables from a fixed experiment run.

These checks should be completed before treating the model as evidence for an
operational decision.

## 6. Data preparation and feature engineering

The training code selects four raw numeric features in a fixed order:

```python
['Oil_Rate', 'Water_Cut', 'Pressure', 'Temperature']
```

No explicit imputation, scaling, encoding, outlier treatment, lag features,
rolling statistics, trend features, or timestamp-derived features are applied.
This is acceptable for Random Forests and for the controlled synthetic data,
but it limits the model's ability to identify deterioration over time.

The inference feature list in `predict.py` mirrors the training list, which
avoids column-order mismatch. The latest reading is selected after ordering a
well's records by the ISO-formatted date.

Recommended production preparation includes schema validation, numeric range
checks, missing-data policy, sensor-quality flags, and temporal features such as
recent change, rolling mean, rolling standard deviation, and deviation from a
well-specific baseline.

## 7. Label quality and leakage considerations

The label is generated from the same simulation logic that creates the sensor
signature. This is intentional for a demonstrator, but it is not equivalent to
independent maintenance or failure records. Real deployment requires labels
from confirmed work orders, failure logs, or inspection outcomes, together with
a clearly defined prediction horizon.

The current target is the status of the same reading. The code does not define
whether the intended task is:

- detecting a failure already present;
- predicting a failure within the next day; or
- predicting a failure within a future maintenance window.

For a genuine predictive-maintenance use case, labels should be shifted into
the future and features must be restricted to information available at the
prediction timestamp. A time-based split is then required to prevent future
information from entering model development.

## 8. Modeling approach

`train_model.py` uses:

- `RandomForestClassifier`
- 100 trees (`n_estimators=100`)
- maximum depth 5 (`max_depth=5`)
- fixed `random_state=42`
- stratified 80/20 `train_test_split`

Random Forest is a sensible baseline for mixed-scale numeric sensor data
because it does not require feature standardization and can represent
non-linear relationships. The shallow tree depth is a reasonable first
regularization choice.

The model is serialized with `joblib` to
`models/pump_failure_model.pkl`. `predict.py` lazy-loads and caches this model
so the GUI does not reload it on every diagnostic request.

Missing modeling components include a baseline classifier, hyperparameter
search, cross-validation, class-weight/cost analysis, feature importance
review, probability calibration, and model/version metadata.

## 9. Evaluation methodology

The training script evaluates the held-out test set using:

- `classification_report`, which prints precision, recall, F1-score, and
  support;
- ROC AUC from held-out predicted probabilities.

The split is stratified, which is appropriate for the imbalanced failure class.
However, a random row split is optimistic for time-series and repeated
well-level observations because readings from the same well and adjacent days
can appear in both train and test sets. It does not measure performance on
future dates or on unseen wells.

No executed metric output is persisted in the repository, so this report does
not claim a numeric accuracy, F1, recall, or AUC. The comment in
`train_model.py` identifies 0.85 as an informal AUC aim, but that is not a
validated acceptance criterion.

A stronger evaluation design would use:

1. chronological train/validation/test partitions;
2. a final untouched future test period;
3. grouped or leave-one-well-out validation when generalization to new wells
   matters;
4. repeated runs or confidence intervals;
5. threshold selection based on the relative costs of missed failures and
   unnecessary inspections;
6. PR AUC, recall at an acceptable alert volume, precision, false-alert rate,
   and calibration error in addition to ROC AUC.

## 10. Deployment and user workflow

The operational path is implemented in `app.py`:

1. A user selects a well.
2. The latest stored reading is passed to the cached model.
3. The score is mapped to NORMAL, WARNING, or CRITICAL.
4. Technical and stakeholder reports are refreshed.
5. Charts are updated.
6. CRITICAL wells trigger a technical report attachment and an email alert.

The application includes useful prototype safeguards: missing-model guidance,
empty-well validation, logging, report generation, idempotent data loads, and
dry-run email behavior when credentials are absent.

Important production limitations remain:

- inference depends on the current working directory because paths are
  relative;
- model and data schemas are not versioned together;
- alerts are suppressed only per well per GUI session, not via a durable alert
  history or cooldown policy;
- there is no API or scheduled batch scoring service;
- email delivery and dashboard execution are coupled to the desktop process;
- no authentication, authorization, audit trail, or secrets-management
  integration is provided.

## 11. Reproducibility and data governance

Positive reproducibility features include fixed random seeds, explicit feature
lists, fixed model parameters, a documented pipeline order, and generated
artifacts in conventional locations.

The following should be added for a traceable experiment:

- a training run identifier and timestamp;
- dataset hash and row counts;
- feature schema and data-quality summary;
- train/validation/test date ranges;
- model hyperparameters and library versions;
- all evaluation metrics and confusion matrices;
- serialized threshold-selection evidence;
- model artifact metadata and approval status.

The repository should also keep generated databases, CSVs, logs, and binary
models out of source control unless they are deliberately versioned demo
fixtures. The README states that these artifacts are not tracked, which is
appropriate for generated data.

## 12. Recommended improvement roadmap

### Priority 1: make the experiment trustworthy

1. Replace or supplement synthetic data with validated historical sensor and
   maintenance records.
2. Define the prediction horizon and create future-oriented labels.
3. Add schema/range/missingness validation before training and ingestion.
4. Use chronological and grouped validation, retaining a final future test set.
5. Persist metrics, confusion matrices, PR curves, and the exact training
   configuration.

### Priority 2: improve predictive usefulness

1. Add lag, rolling, trend, and well-baseline features.
2. Compare Random Forest with a simple baseline and a calibrated gradient
   boosting model.
3. Tune the alert threshold using maintenance costs and alert capacity.
4. Measure recall for failures, false alerts per well-month, lead time, and
   calibration rather than relying mainly on ROC AUC.

### Priority 3: productionize operations

1. Resolve the raw-CSV versus default-CSV pipeline mismatch.
2. Use configuration-relative absolute paths rather than the process
   working directory.
3. Add durable alert history, deduplication, cooldowns, and escalation.
4. Add scheduled scoring, model health checks, drift detection, and retraining
   approval.
5. Separate the inference service from the desktop UI and secure credentials
   through a managed secret store.

## 13. Overall assessment

**Methodological maturity:** proof of concept / early prototype.  
**Engineering completeness:** strong for a small demonstrator; the data,
  database, model, reporting, UI, and alerting surfaces are connected.  
**ML evidence strength:** low to moderate for the synthetic demo, insufficient
  for real operational deployment until temporal validation, independent
  labels, calibration, threshold justification, and monitoring are added.

The project is therefore suitable for demonstrating a complete data-science
workflow and for guiding further development, but its current model scores
should not be interpreted as validated real-world failure probabilities.
