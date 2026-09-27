# iptv/channel.py
import json
from . import constants
from .utils import clean_channel_name, normalize_channel_name


class ChannelCollector:
    def __init__(self, cfg, http, logger):
        self.cfg, self.http, self.logger = cfg, http, logger

    def fetch(self):
        # ★ 调试：打印当前 session 里的 cookies
        cookies = self.http.session.cookies.get_dict()
        self.logger.info(f"fetch 前 cookies: {cookies}")

        self.logger.info("拉取频道列表...")
        params = {
            "varName": "channelData",
            "fileds": "-1",
            "isJson": "-1",
            "isAjax": "1",
            "isCountryChannel": str(constants.IS_COUNTRY_CHANNEL),
            "stbType": self.cfg.stb_type,
        }
        referer = self.http.url("/diyiyingshi/en/channel/channelCore.jsp")
        text = self.http.get(constants.PATH_CHANNEL_LIST, params, referer)

        # ★ 调试：打印响应信息
        if text:
            self.logger.info(f"频道列表响应长度: {len(text)}")
            self.logger.info(f"频道列表响应前 200 字: {text[:200]}")
        else:
            self.logger.error("频道列表响应为空（None）")
            return []

        if not text.strip():
            self.logger.error("频道列表响应为空字符串")
            return []

        try:
            data = json.loads(text)
            total = sum(len(c["chanList"]) for c in data)
            self.logger.info(f"  ✅ 解析成功: {len(data)} 栏目, {total} 频道")
            return data
        except json.JSONDecodeError as e:
            self.logger.error(f"解析失败: {e}")
            self.logger.error(f"响应前 500 字: {text[:500]}")
            return []

    def flatten(self, channels):
        """扁平化 + 清洗频道名"""
        seen = {}
        cleaned = 0
        for cat in channels:
            for ch in cat.get("chanList", []):
                idx = ch["channelIndex"]
                if idx not in seen:
                    raw = ch["channelName"]
                    clean = clean_channel_name(raw)
                    if raw != clean:
                        cleaned += 1
                    seen[idx] = {
                        "channelIndex": idx,
                        "channelName": clean,
                        "channelNameRaw": raw,
                        "channelID": ch["channelID"],
                        "timeShift": ch.get("timeShift"),
                        "isTVOD": ch.get("isTVOD"),
                        "hasSubscrib": ch.get("hasSubscrib"),
                        "category": cat.get("chanName", ""),
                    }
        if cleaned:
            self.logger.info(f"  清洗了 {cleaned} 个频道名")
        result = sorted(seen.values(), key=lambda x: x["channelIndex"])
        self.logger.info(f"  扁平化后 {len(result)} 个唯一频道")
        return result


def is_4k_name(name: str) -> bool:
    n = name.lower()
    return "4k" in n or "超高清" in n


def merge_missing_4k(channels, channel_infos, logger):
    """
    运营商 channelList.jsp 不含 4K 频道，仅在 getchannellistHWCTC.jsp 响应下发
    （原始抓包证实：channelList 344 条无 4K，getchannellist 含北京卫视4K/广东卫视4K 等）。
    将频道列表缺失的 4K 频道从 getchannellist 解析结果注入。
    清洗后同名的只保留 UserChannelID 较小者（如 北京卫视4K. 与 北京卫视4K）。
    """
    if not channel_infos:
        return channels
    existing_ids = {str(c.get("channelID")) for c in channels}
    existing_names = {normalize_channel_name(c.get("channelName", "")) for c in channels}
    candidates = []
    for cid, info in channel_infos.items():
        raw_name = info.get("channel_name", "")
        name = clean_channel_name(raw_name)
        if not name or not is_4k_name(name):
            continue
        # 排除名单在 filter_channels 阶段已生效，注入阶段同样拦截（如 江苏晚会4K）
        if raw_name in constants.EXCLUDE_CHANNELS or name in constants.EXCLUDE_CHANNELS:
            continue
        if str(cid) in existing_ids:
            continue
        if normalize_channel_name(name) in existing_names:
            continue
        try:
            idx = int(info.get("user_channel_id") or 9999)
        except ValueError:
            idx = 9999
        candidates.append({
            "channelIndex": idx,
            "channelName": name,
            "channelNameRaw": raw_name,
            "channelID": str(cid),
            "timeShift": info.get("timeshift"),
            "isTVOD": 1,
            "hasSubscrib": 1,
            "category": "4K频道",
        })
    # 同名去重，保留 channelIndex 较小者
    by_name = {}
    for c in sorted(candidates, key=lambda x: x["channelIndex"]):
        by_name.setdefault(normalize_channel_name(c["channelName"]), c)
    added = sorted(by_name.values(), key=lambda x: x["channelIndex"])
    if added:
        logger.info(f"注入缺失 4K 频道 {len(added)} 个: "
                    + ", ".join(c["channelName"] for c in added))
    return channels + added