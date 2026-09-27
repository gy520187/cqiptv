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


# ========== 频道分类规则 ==========
# 数据源的 category 字段全为"全部", 无分类价值, 故按频道名关键词推导分组
# 顺序匹配, 第一命中生效; 新频道落到"其他"时在此补关键词即可
CATEGORY_RULES = [
    ("重庆本地", ("CQTV", "重庆")),
    ("央视频道", ("CCTV", "CGTN", "央视")),
    ("卫视频道", ("卫视",)),
    ("少儿卡通", ("卡酷", "金鹰", "嘉佳", "动漫", "早期教育")),
    ("剧场电影", ("CHC", "剧场", "精彩影视", "金色频道")),
    ("付费专题", ("风云", "世界地理", "兵器科技", "文物宝库", "求索", "书画",
                "高尔夫", "游戏", "快乐垂钓", "女性时尚", "生活时尚", "法治天地",
                "卫生健康", "梨园", "武术世界", "电视指南", "东方财经", "乐游",
                "多彩文体")),
    ("教育", ("CETV", "教育")),
]
DEFAULT_CATEGORY = "其他"


def categorize_channel(name: str) -> str:
    """按频道名推导分组 (顺序匹配, 第一命中生效)"""
    if not name:
        return DEFAULT_CATEGORY
    for group, keywords in CATEGORY_RULES:
        if any(kw in name for kw in keywords):
            return group
    return DEFAULT_CATEGORY


def fmt14_to_iso(fmt14: str) -> str:
    s = str(fmt14)
    if len(s) != 14:
        return ""
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"