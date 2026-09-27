# iptv/epg.py
import json
import time
from . import constants


class EPGCollector:
    def __init__(self, cfg, http, logger):
        self.cfg, self.http, self.logger = cfg, http, logger

    def _fetch_day(self, channel_id, date_index):
        """
        请求参数与原始抓包 e.txt 的回看节目单请求对齐：
        tVodProgramList.jsp?channelId=&dateIndex=&dateSize=2&tVodNumPerPage=999（无 columnId）
        Referer 指向 channelPlayingList.html
        """
        params = {
            "channelId": channel_id,
            "dateIndex": date_index,
            "dateSize": constants.EPG_DATE_SIZE,
            "tVodNumPerPage": constants.EPG_PER_DAY,
        }
        referer = self.http.url("/diyiyingshi/en/channel/channelPlayingList.html")
        text = self.http.get(constants.PATH_EPG, params, referer)
        if not text:
            return None, []
        try:
            data = json.loads(text)
        except Exception:
            self.logger.debug(f"  dateIndex={date_index} 响应非 JSON，跳过")
            return None, []
        if not isinstance(data, list) or len(data) < 2:
            return None, []
        pages = data[1].get("data", []) or []
        programs = [
            p
            for group in pages
            if isinstance(group, list)
            for p in group
            if isinstance(p, dict)
        ]
        return data[0], programs

    def fetch(self, channel_id):
        """
        运营商接口一次只返回 dateIndex 对应一天的节目单（原始抓包证实：
        dateSize=8 的响应也只有当天 36 条节目），逐天请求拼出多日 EPG。
        返回结构保持 programs 为"页"嵌套（每天一页），storage/xmltv 无需改动。
        """
        dates = []
        days = []
        seen = set()
        for day in range(constants.DATE_SIZE):
            info, programs = self._fetch_day(channel_id, day)
            if info and not dates:
                dates = info.get("data", []) or []
            fresh = []
            for p in programs:
                key = (p.get("beginTimeFormat"), p.get("endTimeFormat"), p.get("programName"))
                if key in seen:
                    continue
                seen.add(key)
                fresh.append(p)
            if fresh:
                days.append(fresh)
            time.sleep(constants.INTERVAL)
        return {
            "dates": dates,
            "programs": days,
        }

    def fetch_all(self, channels):
        total = len(channels)
        if constants.MAX_CHANNELS > 0:
            total = min(total, constants.MAX_CHANNELS)
        self.logger.info(f"采集节目单，{total} 频道 × {constants.DATE_SIZE} 天")
        result = {}
        for i, ch in enumerate(channels[:total]):
            cid = ch["channelID"]
            self.logger.info(f"  [{i+1}/{total}] {ch['channelName']}")
            epg = self.fetch(cid)
            n_days = len(epg["programs"])
            n_progs = sum(len(d) for d in epg["programs"])
            self.logger.info(f"    {n_days} 天 / {n_progs} 条节目")
            result[cid] = epg
            time.sleep(constants.INTERVAL)
        return result
