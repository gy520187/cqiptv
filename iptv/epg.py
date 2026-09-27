# iptv/epg.py
import json
import time
from . import constants


class EPGCollector:
    def __init__(self, cfg, http, logger):
        self.cfg, self.http, self.logger = cfg, http, logger

    def fetch(self, channel_id):
        params = {
            "columnId": "",
            "channelId": channel_id,
            "dateIndex": 0,
            "dateSize": constants.DATE_SIZE,
            "tVodNumPerPage": constants.PER_PAGE,
        }
        referer = self.http.url("/diyiyingshi/en/channel/channelCore.jsp")
        text = self.http.get(constants.PATH_EPG, params, referer)
        if not text:
            return {}
        try:
            data = json.loads(text)
            if len(data) < 2:
                return {}
            return {
                "dates": data[0].get("data", []),
                "curDataNum": data[0].get("curDataNum"),
                "totalCount": data[1].get("totalCount"),
                "programs": data[1].get("data", []),
            }
        except Exception:
            return {}

    def fetch_all(self, channels):
        total = len(channels)
        if constants.MAX_CHANNELS > 0:
            total = min(total, constants.MAX_CHANNELS)
        self.logger.info(f"采集节目单，{total} 频道")
        result = {}
        for i, ch in enumerate(channels[:total]):
            self.logger.info(f"  [{i+1}/{total}] {ch['channelName']}")
            result[ch["channelID"]] = self.fetch(ch["channelID"])
            time.sleep(constants.INTERVAL)
        return result