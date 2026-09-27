# tools/download_icons.py
"""独立图标下载工具: python tools/download_icons.py"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iptv.config import load_config
from iptv.logger import setup_logger
from iptv import constants
from iptv.icon import IconHandler


def main():
    cfg = load_config("config.yaml")
    logger = setup_logger(cfg)
    path = os.path.join(constants.OUTPUT_DIR, "channels.json")
    if not os.path.exists(path):
        logger.error(f"未找到 {path}，请先采集")
        return
    with open(path, "r", encoding="utf-8") as f:
        channels = json.load(f)
    logger.info(f"读取 {len(channels)} 个频道")
    handler = IconHandler(cfg, logger)
    stats = handler.ensure_all(channels, force=True)
    logger.info(f"完成: {stats}")


if __name__ == "__main__":
    main()