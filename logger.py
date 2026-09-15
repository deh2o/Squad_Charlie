"""
logger.py
Centralized logging system for the Digital Oilfield Monitoring System.

Logs all system events, errors, and operations to both file and console
for debugging and monitoring purposes.
"""

import logging
import os
from datetime import datetime
from config import COLORS

# Log file configuration
LOG_DIR = 'logs'
LOG_FILE = os.path.join(LOG_DIR, 'system.log')

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
def setup_logger():
    """Set up the centralized logging system."""
    # Create logger
    logger = logging.getLogger('oilfield_monitoring')
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # File handler - detailed logging
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)

    # Console handler - important messages only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Global logger instance
logger = setup_logger()

def log_email_event(event_type, details, level='info'):
    """Log email-related events specifically.

    Args:
        event_type: Type of email event (e.g., 'send_attempt', 'send_success', 'send_failed')
        details: Detailed information about the event
        level: Log level ('info', 'warning', 'error')
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"EMAIL: {event_type} - {details}")

def log_database_event(event_type, details, level='info'):
    """Log database-related events specifically.

    Args:
        event_type: Type of database event (e.g., 'load_csv', 'query', 'error')
        details: Detailed information about the event
        level: Log level ('info', 'warning', 'error')
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"DATABASE: {event_type} - {details}")

def log_model_event(event_type, details, level='info'):
    """Log ML model-related events specifically.

    Args:
        event_type: Type of model event (e.g., 'prediction', 'training', 'error')
        details: Detailed information about the event
        level: Log level ('info', 'warning', 'error')
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"MODEL: {event_type} - {details}")

def log_gui_event(event_type, details, level='info'):
    """Log GUI-related events specifically.

    Args:
        event_type: Type of GUI event (e.g., 'button_click', 'user_action', 'error')
        details: Detailed information about the event
        level: Log level ('info', 'warning', 'error')
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"GUI: {event_type} - {details}")

def log_system_error(error_type, error_message, exception=None):
    """Log system errors with detailed information.

    Args:
        error_type: Category of error (e.g., 'smtp_error', 'database_error')
        error_message: Human-readable error message
        exception: Exception object if available
    """
    logger.error(f"SYSTEM ERROR: {error_type} - {error_message}")
    if exception:
        logger.error(f"Exception details: {str(exception)}", exc_info=True)

def get_recent_logs(lines=50):
    """Get recent log entries for display.

    Args:
        lines: Number of recent lines to retrieve

    Returns:
        List of recent log lines
    """
    try:
        with open(LOG_FILE, 'r') as f:
            all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except FileNotFoundError:
        return ["Log file not found."]
    except Exception as e:
        return [f"Error reading log file: {str(e)}"]

def clear_logs():
    """Clear the log file (use with caution)."""
    try:
        with open(LOG_FILE, 'w') as f:
            f.write(f"Log cleared at {datetime.now()}\n")
        logger.info("Log file cleared")
    except Exception as e:
        logger.error(f"Failed to clear log file: {str(e)}")

if __name__ == "__main__":
    # Test the logging system
    logger.info("Logging system initialized")
    log_email_event('test', 'Testing email logging')
    log_database_event('test', 'Testing database logging')
    log_system_error('test_error', 'Testing error logging')
    print(f"Logging system test complete. Check {LOG_FILE}")
