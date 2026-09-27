# iptv/utils.py
import re


def clean_channel_name(name: str) -> str:
    """清洗频道名（去末尾符号 + 去多余空格）"""
    if not name:
        return ""
    n = name.strip()
    n = re.sub(r"[.。·]+$", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def normalize_channel_name(name: str) -> str:
    """归一化频道名（分组/图标/M3U 用）"""
    n = clean_channel_name(name)
    n = re.sub(r"[（(]高清[)）]", "", n)
    n = re.sub(r"HD$", "", n, flags=re.IGNORECASE)
    n = re.sub(r"[.。·]+$", "", n)
    return n.strip()


GROUP_TITLE_MAP = {
    "央视": "央视频道",
    "卫视": "卫视频道",
    "本地": "重庆本地",
    "高清": "高清频道",
    "特色": "特色频道",
}


def map_group_title(cat: str) -> str:
    return GROUP_TITLE_MAP.get(cat, cat)


def fmt14_to_iso(fmt14: str) -> str:
    s = str(fmt14)
    if len(s) != 14:
        return ""
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"