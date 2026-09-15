import random
import datetime
import csv

from config import WELL_COUNT, DAYS_OF_HISTORY

random.seed(42)

def generate_rows():
    wells = [f'WELL-0{i}' for i in range(1, WELL_COUNT + 1)]
    start_date = datetime.date(2024, 1, 1)
    rows = []

    for well in wells:
        for day in range(DAYS_OF_HISTORY):
            is_failure = random.random() < 0.15

            pressure = random.uniform(1200, 2800)
            if is_failure:
                pressure *= 0.6
                oil_rate = random.uniform(50, 120)
            else:
                oil_rate = random.uniform(200, 500)

            rows.append((
                well,
                (start_date + datetime.timedelta(days=day)).isoformat(),
                round(oil_rate, 2),
                round(random.uniform(5, 60), 2),
                round(pressure, 2),
                round(random.uniform(60, 120), 2),
                1 if is_failure else 0,
            ))
    return rows


def export_to_csv(rows, csv_path="generated_production_data.csv"):
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Well_ID", "Date", "Oil_Rate", "Water_Cut",
            "Pressure", "Temperature", "Pump_Status"
        ])
        writer.writerows(rows)
    print(f"CSV exported: {csv_path}")


if __name__ == "__main__":
    data_rows = generate_rows()
    export_to_csv(data_rows)

    failures = sum(r[-1] for r in data_rows)
    print(f"Generated {len(data_rows)} rows "
          f"({failures} failure rows, {failures / len(data_rows):.1%})")
