"""CSV row validation for production sensor data."""
import math
import re
from datetime import datetime

import config

EXPECTED_COLUMNS = [
    "Well_ID", "Date", "Oil_Rate", "Water_Cut", "Pressure", "Temperature", "Pump_Status",
]
WELL_ID_PATTERN = re.compile(r"^WELL-\d{2}$")
NUMERIC_LIMITS = config.DATA_LIMITS


def _parse_number(value, field):
    if value is None or str(value).strip() == "":
        return None, f"{field} is missing"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, f"{field} must be numeric"
    if not math.isfinite(number):
        return None, f"{field} must be finite"
    low, high = NUMERIC_LIMITS[field]
    if not low <= number <= high:
        return None, f"{field} must be between {low} and {high}"
    return number, None


def validate_row(row):
    errors = []
    if len(row) != len(EXPECTED_COLUMNS):
        return [f"Expected {len(EXPECTED_COLUMNS)} columns, got {len(row)}"]

    well_id, date, oil, water, pressure, temperature, pump = row
    if not WELL_ID_PATTERN.fullmatch(str(well_id).strip()):
        errors.append("Well_ID must match WELL-XX")
    try:
        datetime.strptime(str(date).strip(), "%Y-%m-%d")
    except ValueError:
        errors.append("Date must be a valid YYYY-MM-DD date")

    for field, value in {
        "Oil_Rate": oil, "Water_Cut": water, "Pressure": pressure,
        "Temperature": temperature,
    }.items():
        _, error = _parse_number(value, field)
        if error:
            errors.append(error)

    if str(pump).strip() not in {"0", "1"}:
        errors.append("Pump_Status must be 0 or 1")
    return errors
