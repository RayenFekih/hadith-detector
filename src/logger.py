import os

ERROR_LOGGING_PATH: str = "logs"
os.makedirs(ERROR_LOGGING_PATH, exist_ok=True)
error_log_file_path = os.path.join(ERROR_LOGGING_PATH, "logs")

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] [%(levelname)s] - %(message)s (%(filename)s:%(lineno)s)",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "verbose",
            "stream": "ext://sys.stdout",
        },
        "error_log_file_handler": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "verbose",
            "filename": "logs/error.log",  # or use your variable
            "mode": "a",
            "maxBytes": 5 * 1024 * 1024,  # 5MB max log size
            "backupCount": 3,
        },
    },
    "root": {"level": "INFO", "handlers": ["console", "error_log_file_handler"]},
}
