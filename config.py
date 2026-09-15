"""
config.py
Shared constants for the Digital Oilfield Monitoring & Predictive
Maintenance System. Every other module imports from here so that
paths, thresholds, and addresses only ever need to change in one place.
"""

# --- File paths -------------------------------------------------------
# All paths are relative to the project root, so every script must be run
# from the project root (e.g. `python app.py`, not `python src/app.py`).
DB_PATH = 'data/oilfield.db'            # SQLite database, created by db_setup.py
CSV_PATH = 'data/production_data.csv'   # written by generate_data.py, read by load_csv.py
MODEL_PATH = 'models/pump_failure_model.pkl'  # trained model, saved by train_model.py
REPORTS_DIR = 'reports'                 # where reports.py writes .txt files for emailing

# --- Email --------------------------------------------------------------
# Hardcoded per FR4: automatic alerts always go to the technical team,
# no user input required.
TECH_EMAIL = 'tech-team@example.com'

# Gmail account the alerts are sent FROM. The matching app password is read
# from the EMAIL_PASS environment variable at send time (never stored here).
SENDER_EMAIL = 'yourproject@gmail.com'
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587  # STARTTLS. Use 465 with SMTP_SSL if your network blocks 587.

# --- ML -----------------------------------------------------------------
# Failure probability tiers used by predict.get_risk_level() and the GUI.
RISK_THRESHOLD = 0.75  # >= this is CRITICAL and triggers an automatic email alert (FR4)
WARNING_THRESHOLD = 0.50  # >= this is WARNING; below it the well is NORMAL

# --- Data simulation ------------------------------------------------------
WELL_COUNT = 5        # WELL-01 .. WELL-05
DAYS_OF_HISTORY = 30  # consecutive days of readings per well