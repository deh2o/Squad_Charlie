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

`data/oilfield.db`, `data/production_data.csv` and the model file are generated
locally and are not tracked in git. Rows are keyed on `(Well_ID, Date)`, so
`load_csv.py` can be re-run without duplicating data.
