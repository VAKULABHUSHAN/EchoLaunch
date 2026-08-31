import logging
import os
import sys

def setup_logger(name: str, log_file: str = "logs/activity.log", level=logging.INFO) -> logging.Logger:
    """Sets up a logger that outputs to both console and a log file."""
    logger = logging.getLogger(name)
    
    # Avoid adding multiple handlers if setup is called multiple times
    if logger.hasHandlers():
        return logger

    logger.setLevel(level)

    # Ensure logs directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Formatter
    formatter = logging.Formatter(
        '[%(levelname)s] %(asctime)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler (cleaner output for user)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)

    # File Handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
