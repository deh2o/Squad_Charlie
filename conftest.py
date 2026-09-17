"""
conftest.py
Pytest fixtures for the Digital Oilfield Monitoring System.

Provides reusable test fixtures for database, model, and sample data
across all test modules.
"""

import os
import tempfile
import shutil
import sqlite3
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib

# Import application modules
import config
import db_setup
import data_loader
import generate_data
import load_csv
import train_model
import predict


@pytest.fixture(scope="session")
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def temp_db_path(temp_dir):
    """Create a temporary database path for testing."""
    os.makedirs(temp_dir, exist_ok=True)
    db_path = os.path.join(temp_dir, "test_oilfield.db")
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="function")
def temp_model_path(temp_dir):
    """Create a temporary model path for testing."""
    os.makedirs(temp_dir, exist_ok=True)
    model_path = os.path.join(temp_dir, "test_model.pkl")
    yield model_path
    if os.path.exists(model_path):
        os.remove(model_path)


@pytest.fixture(scope="function")
def temp_csv_path(temp_dir):
    """Create a temporary CSV path for testing."""
    os.makedirs(temp_dir, exist_ok=True)
    csv_path = os.path.join(temp_dir, "test_data.csv")
    yield csv_path
    if os.path.exists(csv_path):
        os.remove(csv_path)


@pytest.fixture(scope="function")
def mock_config(temp_db_path, temp_model_path, temp_csv_path, temp_dir):
    """Override config paths with temporary paths for testing."""
    original_db_path = config.DB_PATH
    original_model_path = config.MODEL_PATH
    original_csv_path = config.CSV_PATH
    original_reports_dir = config.REPORTS_DIR
    
    config.DB_PATH = temp_db_path
    config.MODEL_PATH = temp_model_path
    config.CSV_PATH = temp_csv_path
    config.REPORTS_DIR = temp_dir
    
    yield
    
    config.DB_PATH = original_db_path
    config.MODEL_PATH = original_model_path
    config.CSV_PATH = original_csv_path
    config.REPORTS_DIR = original_reports_dir


@pytest.fixture(scope="function")
def test_database(mock_config):
    """Create a test database with the production_data schema."""
    db_setup.create_database()
    return config.DB_PATH


@pytest.fixture(scope="function")
def sample_well_data():
    """Generate sample well data for testing."""
    np.random.seed(42)
    
    data = []
    well_ids = ['WELL-01', 'WELL-02', 'WELL-03']
    start_date = datetime(2024, 1, 1)
    
    for well_id in well_ids:
        for day in range(30):  # 30 days of data
            date = start_date + timedelta(days=day)
            
            # Generate realistic sensor readings
            oil_rate = np.random.uniform(50, 200)
            water_cut = np.random.uniform(5, 40)
            pressure = np.random.uniform(1000, 3000)
            temperature = np.random.uniform(60, 120)
            
            # Pump status: mostly normal (0), occasional failures (1)
            pump_status = 1 if np.random.random() < 0.1 else 0
            
            data.append({
                'Well_ID': well_id,
                'Date': date.strftime('%Y-%m-%d'),
                'Oil_Rate': oil_rate,
                'Water_Cut': water_cut,
                'Pressure': pressure,
                'Temperature': temperature,
                'Pump_Status': pump_status
            })
    
    return pd.DataFrame(data)


@pytest.fixture(scope="function")
def sample_csv_file(sample_well_data, temp_csv_path):
    """Create a sample CSV file with test data."""
    sample_well_data.to_csv(temp_csv_path, index=False)
    return temp_csv_path


@pytest.fixture(scope="function")
def populated_database(test_database, sample_csv_file):
    """Load sample data into the test database."""
    load_csv.load_csv_into_db(sample_csv_file)
    return test_database


@pytest.fixture(scope="function")
def trained_model(populated_database, temp_model_path):
    """Train a model with sample data for testing."""
    train_model.train_model()
    return temp_model_path


@pytest.fixture(scope="function")
def mock_smtp_config():
    """Set up mock SMTP configuration for testing."""
    original_smtp_host = config.SMTP_HOST
    original_smtp_port = config.SMTP_PORT
    original_email_pass = config.EMAIL_PASS
    original_sender_email = config.SENDER_EMAIL
    original_tech_email = config.TECH_EMAIL
    
    # Set test values
    config.SMTP_HOST = 'smtp.test.com'
    config.SMTP_PORT = 587
    config.EMAIL_PASS = 'test_password'
    config.SENDER_EMAIL = 'test_sender@example.com'
    config.TECH_EMAIL = 'test_tech@example.com'
    
    yield
    
    config.SMTP_HOST = original_smtp_host
    config.SMTP_PORT = original_smtp_port
    config.EMAIL_PASS = original_email_pass
    config.SENDER_EMAIL = original_sender_email
    config.TECH_EMAIL = original_tech_email


@pytest.fixture(scope="function")
def clear_model_cache():
    """Clear the model cache between tests."""
    predict._model = None
    yield
    predict._model = None


@pytest.fixture(scope="function")
def sample_well_prediction(populated_database, trained_model, clear_model_cache):
    """Get a sample prediction for testing."""
    well_ids = data_loader.get_well_ids()
    if well_ids:
        well_id = well_ids[0]
        risk_score = predict.predict_failure_risk(well_id)
        risk_level = predict.get_risk_level(risk_score)
        return {
            'well_id': well_id,
            'risk_score': risk_score,
            'risk_level': risk_level
        }
    return None


@pytest.fixture(scope="function")
def mock_logger():
    """Create a mock logger for testing."""
    import logger
    
    # Clear any existing logs
    if os.path.exists(logger.LOG_FILE):
        os.remove(logger.LOG_FILE)
    
    yield logger
    
    # Clean up log file after test
    if os.path.exists(logger.LOG_FILE):
        os.remove(logger.LOG_FILE)


@pytest.fixture(scope="function")
def mock_email():
    """Mock email functionality for testing."""
    original_email_pass = config.EMAIL_PASS
    
    # Set to None to trigger dry run mode
    config.EMAIL_PASS = None
    
    yield
    
    config.EMAIL_PASS = original_email_pass