# iptv/epg.py
import json
import time
from . import constants
from .channel import is_4k_name, base_channel_name
from .utils import normalize_channel_name


def alt_ids_for(channel, alias_map):
    """
    频道 EPG 备用 ID 列表。
    4K/超高清频道优先套用基础(高清)频道 ID——运营商将 4K 卫视频道的
    节目单挂在对应高清频道 ID 下；再附加同名 4K 变体 ID。
    普通频道直接取同名变体 ID。均排除主 ID，保持首次出现顺序。
    """
    name = channel.get("channelName", "")
    n = normalize_channel_name(name)
    alts = []
    if is_4k_name(name):
        base = base_channel_name(name)
        if base and base != n:
            alts.extend(alias_map.get(base, []))
    alts.extend(alias_map.get(n, []))
    primary = str(channel.get("channelID"))
    return [a for a in dict.fromkeys(alts) if a != primary]


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

    def _fetch_days(self, channel_id):
        """逐天拉取一个频道 ID 的全部节目（dateIndex 0..7），按 (起止,标题) 去重"""
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
        return dates, days

    def fetch(self, channel_id, alt_ids=None):
        """
        运营商接口一次只返回 dateIndex 对应一天的节目单（原始抓包证实：
        dateSize=8 的响应也只有当天 36 条节目），逐天请求拼出多日 EPG。
        同名频道存在高清/SD 等变体时，tVod 数据可能只挂在某个 ID 上
        （实测 云南卫视(高清)=642905769 无数据，SD 变体=1672 有）：
        主 ID 8 天全空则依次回退备用 ID。返回仍按主 channelID 语义使用。
        """
        dates, days = self._fetch_days(channel_id)
        if not days and alt_ids:
            for alt in alt_ids:
                self.logger.info(f"    channelId={channel_id} 无节目数据, 回退备用 ID {alt}")
                alt_dates, alt_days = self._fetch_days(alt)
                if alt_days:
                    dates = alt_dates
                    days = alt_days
                    break
        return {
            "dates": dates,
            "programs": days,
        }

    def fetch_all(self, channels, alias_map=None):
        alias_map = alias_map or {}
        total = len(channels)
        if constants.MAX_CHANNELS > 0:
            total = min(total, constants.MAX_CHANNELS)
        self.logger.info(f"采集节目单，{total} 频道 × {constants.DATE_SIZE} 天")
        result = {}
        for i, ch in enumerate(channels[:total]):
            cid = ch["channelID"]
            self.logger.info(f"  [{i+1}/{total}] {ch['channelName']}")
            alt_ids = alt_ids_for(ch, alias_map)
            epg = self.fetch(cid, alt_ids)
            n_days = len(epg["programs"])
            n_progs = sum(len(d) for d in epg["programs"])
            self.logger.info(f"    {n_days} 天 / {n_progs} 条节目")
            result[cid] = epg
            time.sleep(constants.INTERVAL)
        return result
