# tools/check_icons.py
"""检查缺失的图标: python tools/check_icons.py"""
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
    with open(path, "r", encoding="utf-8") as f:
        channels = json.load(f)
    handler = IconHandler(cfg, logger)
    missing = [ch["channelName"] for ch in channels
               if not handler.exists(ch["channelName"])]
    print(f"缺失 {len(missing)} 个图标：")
    for n in missing:
        print(f"  - {n}")
    with open("missing_icons.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(missing))


if __name__ == "__main__":
    main()