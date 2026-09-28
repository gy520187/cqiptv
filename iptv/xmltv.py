# iptv/xmltv.py
import os
import gzip
from xml.sax.saxutils import escape
from . import constants
from .utils import normalize_channel_name


class XMLTVGenerator:
    def __init__(self, cfg, logger):
        self.cfg, self.logger = cfg, logger
        self.tz = "+0800"

    def _t(self, fmt14):
        s = str(fmt14)
        if len(s) != 14:
            return ""
        return f"{s} {self.tz}"

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
            tmp1 = p1 + ".tmp"
            with open(tmp1, "w", encoding="utf-8") as f:
                f.write(xml)
            os.replace(tmp1, p1)
            p2 = os.path.join(constants.OUTPUT_DIR, "epg.xml.gz")
            tmp2 = p2 + ".tmp"
            with gzip.open(tmp2, "wt", encoding="utf-8") as f:
                f.write(xml)
            os.replace(tmp2, p2)
            self.logger.info(f"保存: {p1}, {p2}")
            return p1, p2
        except Exception as e:
            self.logger.error(f"XMLTV 保存失败: {e}", exc_info=True)
            return None, None