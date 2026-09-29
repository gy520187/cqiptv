# iptv/logger.py
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
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

    # 按天轮转，仅保留 1 个昨日备份，更早的日志自动删除
    fh = TimedRotatingFileHandler(
        os.path.join(constants.LOG_DIR, constants.LOG_FILE),
        when="midnight",
        backupCount=1,
        encoding="utf-8",
    )
    fh.suffix = "%Y-%m-%d"
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger