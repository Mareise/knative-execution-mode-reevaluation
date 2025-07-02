import logging
import os

def get_logger(name: str = __name__):
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    logger = logging.getLogger(name)
    if not logger.hasHandlers():  # Avoid duplicate handlers if already configured
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(LOG_LEVEL)

    return logger
