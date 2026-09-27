# iptv/channel.py
import json
from . import constants
from .utils import clean_channel_name


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