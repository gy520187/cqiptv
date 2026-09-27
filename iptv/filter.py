# iptv/filter.py
import re
from typing import List, Dict
from collections import defaultdict
from . import constants
from .utils import normalize_channel_name


def is_hd_channel(name: str) -> bool:
    if not name:
        return False
    n = name.strip()
    if re.search(r"[（(]高清[)）]", n):
        return True
    if re.search(r"HD$", n, re.IGNORECASE):
        return True
    if re.search(r"4K|超高清", n, re.IGNORECASE):
        return True
    return False


def filter_channels(channels: List[dict]) -> List[dict]:
    channels = [c for c in channels
                if c.get("channelName") not in constants.EXCLUDE_CHANNELS]
    groups: Dict[str, List[dict]] = defaultdict(list)
    for ch in channels:
        key = normalize_channel_name(ch.get("channelName", ""))
        groups[key].append(ch)
    result = []
    for key, items in groups.items():
        hd = [c for c in items if is_hd_channel(c.get("channelName", ""))]
        sd = [c for c in items if not is_hd_channel(c.get("channelName", ""))]
        if hd:
            hd.sort(key=lambda x: x.get("channelIndex", 9999))
            result.append(hd[0])
        elif sd:
            sd.sort(key=lambda x: x.get("channelIndex", 9999))
            result.append(sd[0])
        else:
            result.append(items[0])
    result.sort(key=lambda x: x.get("channelIndex", 9999))
    return result