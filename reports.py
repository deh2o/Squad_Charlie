"""
reports.py
Member 3/4 | Wednesday deliverable.

Two views of the same well data for two different audiences:

    technical_report()   -> engineers: raw descriptive statistics
    stakeholder_report() -> managers: production totals and plain language

Both return plain strings so the GUI can drop them straight into a Text
widget and emailer.py can attach the same text as a .txt file.
"""

import os
from datetime import datetime

from config import REPORTS_DIR, RISK_THRESHOLD
from data_loader import load_all_data, load_well_data
from predict import get_risk_level, predict_failure_risk
from field_analytics import build_field_snapshot, well_operational_summary

SENSOR_COLUMNS = ['Oil_Rate', 'Pressure', 'Water_Cut', 'Temperature']

# Report width — keeps the separator lines aligned with the columns that
# pandas' describe() prints.
WIDTH = 72


def _header(title, well_id):
    """Common banner: title, well, and when the report was produced."""
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    return (
        f"{title}\n"
        f"{'=' * WIDTH}\n"
        f"Well:      {well_id}\n"
        f"Generated: {stamp}\n"
        f"{'-' * WIDTH}\n\n"
    )


def technical_report(well_id: str) -> str:
    """Descriptive statistics and the current model risk score."""
    df = load_well_data(well_id)
    if df.empty:
        return f"No data available for {well_id}."

    # describe() gives count/mean/std/min/quartiles/max for each sensor in
    # one call — the engineer's view of how the well behaved this month.
    stats = df[SENSOR_COLUMNS].describe().round(2)
    failures = int(df['Pump_Status'].sum())
    days = len(df)
    latest = df.iloc[-1]

    score = predict_failure_risk(well_id)

    report = _header('TECHNICAL REPORT', well_id)
    report += "SENSOR STATISTICS\n"
    report += stats.to_string() + "\n\n"

    report += "LATEST READING\n"
    report += f"  Date        : {latest['Date']}\n"
    report += f"  Oil rate    : {latest['Oil_Rate']:.2f} bbl/day\n"
    report += f"  Pressure    : {latest['Pressure']:.2f} psi\n"
    report += f"  Water cut   : {latest['Water_Cut']:.2f} %\n"
    report += f"  Temperature : {latest['Temperature']:.2f} C\n\n"

    report += "RELIABILITY\n"
    report += f"  Failure days      : {failures}/{days}\n"
    report += f"  Failure rate      : {failures / days:.1%}\n"
    report += f"  Mean pressure     : {df['Pressure'].mean():.1f} psi\n"
    report += f"  Mean oil rate     : {df['Oil_Rate'].mean():.1f} bbl/day\n\n"

    report += "MODEL DIAGNOSIS\n"
    report += f"  Failure risk      : {score * 100:.1f}%\n"
    report += f"  Risk level        : {get_risk_level(score)}\n"
    report += f"  Alert threshold   : {RISK_THRESHOLD * 100:.0f}%\n"
    return report


def stakeholder_report(well_id: str) -> str:
    """Production totals and a one-word status, with no jargon."""
    df = load_well_data(well_id)
    if df.empty:
        return f"No data available for {well_id}."

    days = len(df)
    failures = int(df['Pump_Status'].sum())
    total_oil = df['Oil_Rate'].sum()
    uptime = (days - failures) / days

    score = predict_failure_risk(well_id)
    level = get_risk_level(score)

    # Managers act on the recommendation, not the number, so each risk tier
    # maps to a specific next step.
    actions = {
        'CRITICAL': 'Schedule immediate inspection — failure likely within days.',
        'WARNING': 'Plan maintenance in the next service window.',
        'NORMAL': 'No action required. Continue routine monitoring.',
    }

    report = _header('FIELD STATUS SUMMARY', well_id)
    report += "PRODUCTION\n"
    report += f"  Total oil produced : {total_oil:,.0f} bbl over {days} days\n"
    report += f"  Daily average      : {df['Oil_Rate'].mean():,.0f} bbl/day\n\n"

    report += "RELIABILITY\n"
    report += f"  Days operational   : {days - failures}/{days} ({uptime:.0%} uptime)\n"
    report += f"  Days with failures : {failures}\n\n"

    report += "OUTLOOK\n"
    report += f"  Current status     : {level}\n"
    report += f"  Failure risk       : {score * 100:.0f}%\n"
    report += f"  Recommended action : {actions[level]}\n"
    return report


def field_summary() -> str:
    """Field-level measured KPIs plus model risk for every well."""
    df = load_all_data()
    if df.empty:
        return "No data loaded. Run generate_data.py then load_csv.py."

    snapshot = build_field_snapshot(df)
    kpis = snapshot["kpis"]
    risk = snapshot["risk"]
    operational = well_operational_summary(df).set_index("Well_ID")

    lines = [
        'FIELD INTELLIGENCE OVERVIEW',
        '=' * WIDTH,
        'FIELD KPIs',
        f"  Wells monitored       : {kpis['well_count']}",
        f"  Observations          : {kpis['observation_count']}",
        f"  Total oil             : {kpis['total_oil']:,.0f} bbl",
        f"  Average field oil/day : {kpis['average_daily_oil']:,.1f} bbl/day",
        f"  Historical failure rate: {kpis['field_failure_rate']:.1%}",
        f"  Historical uptime     : {kpis['field_uptime']:.1%}",
        f"  Average water cut    : {kpis['average_water_cut']:.2f}%",
        f"  Average pressure     : {kpis['average_pressure']:.1f} psi",
        '',
        'MODEL RISK DISTRIBUTION',
        f"  Normal   : {risk['risk_counts'].get('NORMAL', 0)} wells",
        f"  Warning  : {risk['risk_counts'].get('WARNING', 0)} wells",
        f"  Critical : {risk['risk_counts'].get('CRITICAL', 0)} wells",
        f"  Mean 7-day failure risk: {risk['average_failure_risk']:.1%}",
        '',
        'WELL STATUS',
        f"{'Well':<10}{'Oil (bbl)':>14}{'Uptime':>10}{'Risk':>10}{'Level':>12}",
        '-' * WIDTH,
    ]

    for item in risk["wells"]:
        well_id = item["well_id"]
        row = operational.loc[well_id]
        lines.append(
            f"{well_id:<10}{row['Total_Oil']:>14,.0f}"
            f"{row['Uptime']:>10.1%}{item['score']:>9.1%}{item['level']:>12}"
        )

    lines.extend([
        '',
        'INTERPRETATION',
        '  Historical KPIs describe observed field performance.',
        '  Model risk is a forward-looking 7-day prediction and is not a confirmed failure.',
    ])
    return '\n'.join(lines)


def save_report_to_file(text: str, filename: str) -> str:
    """Write a report under reports/ and return its path, for email attachments."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, filename)
    with open(path, 'w') as f:
        f.write(text)
    return path


if __name__ == "__main__":
    # Smoke test: print both reports for the first well plus the field table.
    from data_loader import get_well_ids

    first_well = get_well_ids()[0]
    print(technical_report(first_well))
    print()
    print(stakeholder_report(first_well))
    print()
    print(field_summary())
