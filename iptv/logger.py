# iptv/logger.py
import os
import sys
import logging
from . import constants


def setup_logger(cfg=None) -> logging.Logger:
    os.makedirs(constants.LOG_DIR, exist_ok=True)

    logger = logging.getLogger("iptv")
    logger.setLevel(getattr(logging, constants.LOG_LEVEL.upper()))
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(
        os.path.join(constants.LOG_DIR, constants.LOG_FILE),
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger