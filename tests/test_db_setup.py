"""
test_db_setup.py
Tests for database setup and schema creation.
"""

import os
import sqlite3
import shutil
import pytest
import db_setup
import config
import load_csv


def test_database_creation(test_database):
    """Test that the database is created with the correct schema."""
    assert os.path.exists(test_database)
    
    conn = sqlite3.connect(test_database)
    cursor = conn.cursor()
    
    # Check that the production_data table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='production_data'"
    )
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == 'production_data'
    
    # Check table schema
    cursor.execute("PRAGMA table_info(production_data)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    expected_columns = {
        'Well_ID': 'TEXT',
        'Date': 'TEXT',
        'Oil_Rate': 'REAL',
        'Water_Cut': 'REAL',
        'Pressure': 'REAL',
        'Temperature': 'REAL',
        'Pump_Status': 'INTEGER'
    }
    
    for col_name, col_type in expected_columns.items():
        assert col_name in columns
        assert columns[col_name] == col_type
    
    conn.close()


def test_unique_constraint(test_database):
    """Test that the unique constraint on (Well_ID, Date) is enforced."""
    conn = sqlite3.connect(test_database)
    cursor = conn.cursor()
    
    # Check for unique index
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_well_date'"
    )
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == 'idx_well_date'
    
    conn.close()


def test_database_idempotency(test_database):
    """Test that create_database can be run multiple times without errors."""
    # Should not raise an exception
    db_setup.create_database()
    db_setup.create_database()
    
    assert os.path.exists(test_database)


def test_directory_creation(temp_db_path):
    """Test that the data directory is created if it doesn't exist."""
    # Remove the directory if it exists
    data_dir = os.path.dirname(temp_db_path)
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir, ignore_errors=True)
    
    # Run create_database
    original_db_path = config.DB_PATH
    config.DB_PATH = temp_db_path
    
    db_setup.create_database()
    
    # Check that directory was created
    assert os.path.exists(data_dir)
    assert os.path.exists(temp_db_path)
    
    config.DB_PATH = original_db_path


def test_duplicate_removal(test_database, sample_csv_file):
    """Test that duplicate rows are removed from the database."""
    import load_csv
    
    # Load the same CSV twice
    load_csv.load_csv_into_db(sample_csv_file)
    load_csv.load_csv_into_db(sample_csv_file)
    
    conn = sqlite3.connect(test_database)
    cursor = conn.cursor()
    
    # Count total rows
    cursor.execute("SELECT COUNT(*) FROM production_data")
    total_rows = cursor.fetchone()[0]
    
    # Count unique (Well_ID, Date) combinations
    cursor.execute("SELECT COUNT(DISTINCT Well_ID || Date) FROM production_data")
    unique_rows = cursor.fetchone()[0]
    
    # Should be equal (no duplicates)
    assert total_rows == unique_rows
    
    conn.close()