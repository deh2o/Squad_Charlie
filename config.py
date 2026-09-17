"""
config.py
Shared constants for the Digital Oilfield Monitoring & Predictive
Maintenance System. Every other module imports from here so that
paths, thresholds, and addresses only ever need to change in one place.
"""
import os

# Loading .env is optional: python-dotenv may not be installed on a
# marker's machine, and the app must still start without it.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Email/SMTP configuration from environment variables
# These are loaded from .env file or system environment
TECH_EMAIL = os.environ.get('TECH_EMAIL', 'tech@example.com')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'sender@example.com')
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USE_SSL = os.environ.get('SMTP_USE_SSL', 'false').lower() == 'true'  # For port 465
EMAIL_PASS = os.environ.get('EMAIL_PASS')


# --- File paths -------------------------------------------------------
# All paths are relative to the project root, so every script must be run
# from the project root (e.g. `python app.py`, not `python src/app.py`).
DB_PATH = 'data/oilfield.db'            # SQLite database, created by db_setup.py
CSV_PATH = 'data/production_data.csv'   # written by generate_data.py, read by load_csv.py
RAW_DATA_DIR = 'raw'                    # folder for raw CSV files with random month_year names
MODEL_PATH = 'models/pump_failure_model.pkl'  # trained model, saved by train_model.py
REPORTS_DIR = 'reports'                 # where reports.py writes .txt files for emailing

# --- ML -----------------------------------------------------------------
# Failure probability tiers used by predict.get_risk_level() and the GUI.
RISK_THRESHOLD = 0.75  # >= this is CRITICAL and triggers an automatic email alert (FR4)
WARNING_THRESHOLD = 0.50  # >= this is WARNING; below it the well is NORMAL

# --- User interface -------------------------------------------------------
# One dark palette shared by the Tkinter widgets (app.py) and the Matplotlib
# figures (charts.py), so the embedded charts blend into the window instead
# of showing up as white boxes.
COLORS = {
    'bg': '#0D1117',         # window / chart background
    'panel': '#161B22',      # cards and toolbars
    'border': '#30363D',
    'text': '#E6EDF3',
    'muted': '#8B949E',      # secondary labels, axis ticks
    'accent': '#38bdf8',     # primary actions, oil rate series
    'accent_dark': '#00A383',
    'normal': '#3FB950',     # risk tiers
    'warning': '#D29922',
    'critical': '#F85149',
    'pressure': '#58A6FF',
    'water': '#A371F7',
    'temperature': '#FF9F40',
}

FONT_FAMILY = 'DejaVu Sans'

# --- Data simulation ------------------------------------------------------
WELL_COUNT = 5        # WELL-01 .. WELL-05
DAYS_OF_HISTORY = 30  # consecutive days of readings per well
# Broad sanity bounds used during CSV ingestion. These are validation limits,
# not field-specific operating envelopes.
DATA_LIMITS = {
    'Oil_Rate': (0.0, 10_000.0),
    'Water_Cut': (0.0, 100.0),
    'Pressure': (0.0, 10_000.0),
    'Temperature': (-50.0, 250.0),
}
