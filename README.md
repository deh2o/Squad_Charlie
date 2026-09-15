# squad_charlie
Digital Oil Field Monitoring and Predictive Maintenance System

## Setup

```bash
pip install -r Requirements.txt
# Linux only, for the Tkinter GUI: sudo apt install python3-tk
```

## Data pipeline

Run once, in this order:

```bash
python db_setup.py       # create data/oilfield.db + production_data table
python generate_data.py  # write synthetic readings to data/production_data.csv
python load_csv.py       # load the CSV into the database
python train_model.py    # train the Random Forest, save models/pump_failure_model.pkl
python predict.py        # score every well from the latest reading
```

## Dashboard

```bash
python app.py
```

Select a well, press **Run Diagnostics** to score it, switch charts from the
toolbar, and read the technical / stakeholder reports in the tabs below.
A well scoring at or above the CRITICAL threshold (75%) automatically emails
`TECH_EMAIL` with the technical report attached.

## Email

Copy `.env.example` to `.env` and set `EMAIL_PASS` to a Gmail 16-character
App Password. Without it the app runs in **dry run** mode: messages are
printed to the console instead of sent, so the GUI still demos end to end.

## Modules

| File | Role |
| --- | --- |
| `config.py` | paths, thresholds, email settings, UI palette |
| `db_setup.py` | create the SQLite schema and uniqueness constraint |
| `generate_data.py` | simulate 5 wells × 30 days into the CSV |
| `load_csv.py` | load the CSV into the database (idempotent) |
| `data_loader.py` | read wells and readings back as DataFrames |
| `train_model.py` | train and save the Random Forest classifier |
| `predict.py` | failure probability and NORMAL/WARNING/CRITICAL level |
| `charts.py` | Matplotlib charts embedded in a Tkinter frame |
| `reports.py` | technical, stakeholder and field-overview reports |
| `emailer.py` | Gmail SMTP alerts and report delivery |
| `app.py` | the dashboard that wires it all together |

`data/oilfield.db`, `data/production_data.csv` and the model file are generated
locally and are not tracked in git. Rows are keyed on `(Well_ID, Date)`, so
`load_csv.py` can be re-run without duplicating data.
