"""
config.py
Shared constants for the Digital Oilfield Monitoring & Predictive
Maintenance System. Every other module imports from here so that
paths, thresholds, and addresses only ever need to change in one place.
"""

# --- File paths -------------------------------------------------------
DB_PATH = 'data/oilfield.db'
csv_path = 'production_data.csv'
MODEL_PATH = 'models/pump_failure_model.pkl'
REPORTS_DIR = 'reports'

# --- Email --------------------------------------------------------------
# Hardcoded per FR4: automatic alerts always go to the technical team,
# no user input required.
TECH_EMAIL = 'tech-team@example.com'

# --- ML -----------------------------------------------------------------
RISK_THRESHOLD = 0.75  # > this triggers an automatic email alert (FR4)

# --- Data simulation ------------------------------------------------------
WELL_COUNT = 5
DAYS_OF_HISTORY = 30