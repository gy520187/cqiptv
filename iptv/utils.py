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
    n = re.sub(r"[（(]超高清[)）]", "", n)
    n = re.sub(r"超高清$", "", n)
    n = re.sub(r"[.。·]+$", "", n)
    n = n.strip()
    n = RENAME_MAP.get(n, n)
    return n if n else clean_channel_name(name)


# 显示名重命名映射（归一化后应用）
RENAME_MAP = {
    "CCTV-少儿": "CCTV-14少儿",
}

# 分组规则（正则匹配，顺序匹配第一命中生效）
CATEGORY_RULES = [
    # 央视频道仅保留 CCTV-1~17 数字频道（含 CCTV-5＋、CCTV-4K）
    ("央视频道", (r"^CCTV-(?:[1-9]|1[0-7])(?:\D|$)",)),
    # 其余 4K 频道（北京卫视4K/爱上4K 等）
    ("4K频道", (r"4K", r"4k", r"超高清")),
    # 卫视频道先于重庆本地，使 重庆卫视 归入卫视频道
    ("卫视频道", (r"卫视",)),
    ("重庆本地", (r"CQTV", r"重庆")),
    ("少儿卡通", (r"卡酷", r"金鹰", r"嘉佳", r"动漫", r"早期教育")),
    ("剧场电影", (r"CHC", r"剧场", r"精彩影视", r"金色频道")),
    # 央视系付费频道与 CGTN 归付费专题
    ("付费专题", (r"风云", r"世界地理", r"兵器科技", r"文物宝库", r"求索", r"书画",
                r"高尔夫", r"游戏", r"快乐垂钓", r"女性时尚", r"生活时尚", r"法治天地",
                r"卫生健康", r"梨园", r"武术世界", r"电视指南", r"东方财经", r"乐游",
                r"多彩文体", r"CGTN", r"央视")),
    ("教育", (r"CETV", r"教育")),
]
DEFAULT_CATEGORY = "其他"


def categorize_channel(name: str) -> str:
    """按频道名推导分组 (顺序匹配, 第一命中生效)；先归一化再匹配"""
    if not name:
        return DEFAULT_CATEGORY
    n = normalize_channel_name(name)
    for group, patterns in CATEGORY_RULES:
        if any(re.search(p, n) for p in patterns):
            return group
    return DEFAULT_CATEGORY


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