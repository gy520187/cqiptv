# iptv/xmltv.py
import os
import gzip
from datetime import datetime, timedelta
from xml.sax.saxutils import escape
from . import constants
from .utils import normalize_channel_name


class XMLTVGenerator:
    def __init__(self, cfg, logger):
        self.cfg, self.logger = cfg, logger
        self.src_tz = "+0800"   # 运营商节目时间为北京时间

    def _t(self, fmt14):
        """
        14 位北京时间(YYYYMMDDHHMMSS) -> XMLTV programme start/stop。
        默认输出 UTC 时间 +0000：多数 IPTV 播放器把 XMLTV 时间戳当 UTC 处理，
        若直接给 +0800 会整体偏移 8 小时导致"当前播放"定位失败。
        需要本地时间时置 constants.EPG_UTC_TIME=False，输出原值 +0800。
        """
        s = str(fmt14)
        if len(s) != 14:
            return ""
        try:
            dt = datetime.strptime(s, "%Y%m%d%H%M%S")
        except ValueError:
            return ""
        if constants.EPG_UTC_TIME:
            dt -= timedelta(hours=8)
            return dt.strftime("%Y%m%d%H%M%S") + " +0000"
        return s + " +0800"

    def build(self, channels, epgs):
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<tv generator-info-name="iptv-epg-tool">')

        cid_map = {}
        for ch in channels:
            if not ch or not isinstance(ch, dict):
                continue
            xmltv_id = normalize_channel_name(ch.get("channelName", ""))
            cid_map[ch.get("channelID")] = xmltv_id
            lines.append(f'  <channel id="{escape(xmltv_id)}">')
            lines.append(f'    <display-name lang="zh">{escape(ch.get("channelName", ""))}</display-name>')
            if xmltv_id != ch.get("channelName"):
                lines.append(f'    <display-name lang="zh">{escape(xmltv_id)}</display-name>')
            lines.append('  </channel>')

        count = 0
        for ch in channels:
            if not ch or not isinstance(ch, dict):
                continue
            xmltv_id = cid_map.get(ch.get("channelID"))
            epg = epgs.get(ch.get("channelID"), {})

            # ★ 判空
            if not epg or not isinstance(epg, dict):
                continue

            programs = epg.get("programs", [])
            if not programs:
                continue

            for page in programs:
                if not page:
                    continue
                for prog in page:
                    if not prog or not isinstance(prog, dict):
                        continue
                    start = self._t(prog.get("beginTimeFormat"))
                    stop = self._t(prog.get("endTimeFormat"))
                    if not start or not stop:
                        continue
                    lines.append(f'  <programme start="{start}" stop="{stop}" channel="{escape(xmltv_id)}">')
                    lines.append(f'    <title lang="zh">{escape(str(prog.get("programName", "")))}</title>')
                    if prog.get("contentId"):
                        lines.append(f'    <episode-num system="onscreen">{escape(str(prog["contentId"]))}</episode-num>')
                    lines.append('  </programme>')
                    count += 1

        lines.append('</tv>')
        self.logger.info(f"XMLTV: {len(channels)} 频道, {count} 节目")
        return "\n".join(lines)

    def save(self, channels, epgs):
        try:
            os.makedirs(constants.OUTPUT_DIR, exist_ok=True)
            xml = self.build(channels, epgs)
            p1 = os.path.join(constants.OUTPUT_DIR, "epg.xml")
            with open(p1, "w", encoding="utf-8") as f:
                f.write(xml)
            p2 = os.path.join(constants.OUTPUT_DIR, "epg.xml.gz")
            with gzip.open(p2, "wt", encoding="utf-8") as f:
                f.write(xml)
            self.logger.info(f"保存: {p1}, {p2}")
            return p1, p2
        except Exception as e:
            self.logger.error(f"XMLTV 保存失败: {e}", exc_info=True)
            return None, None