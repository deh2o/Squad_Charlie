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
    'accent': '#00D4AA',     # primary actions, oil rate series
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