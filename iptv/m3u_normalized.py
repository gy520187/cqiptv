# iptv/m3u_normalized.py
import os
import re
import urllib.parse
from . import constants
from .utils import normalize_channel_name, categorize_channel


class NormalizedM3UGenerator:
    def __init__(self, cfg, logger):
        self.cfg, self.logger = cfg, logger

    def build_logo(self, name):
        n = normalize_channel_name(name)
        n = re.sub(r'[\\/:*?"<>|]', "_", n)
        return f"{constants.ICON_HOST}/data/icon/{urllib.parse.quote(n)}.png"

    def build_catchup_source(self, timeshift_url):
        if not timeshift_url:
            return ""
        base = timeshift_url.split("?")[0]
        return f"{base}?playseek={{utc:YmdHMS}}-{{utcend:YmdHMS}}&r2h-seek-offset={constants.R2H_SEEK_OFFSET}"

    def build_live_url(self, channel_url, fcc_ip, fcc_port):
        if not channel_url:
            return ""
        url = channel_url.replace("igmp://", "rtp://")
        if fcc_ip and fcc_port:
            url += f"?fcc={fcc_ip}:{fcc_port}"
        return url

    @staticmethod
    def _cctv_sort_key(name):
        """央视频道排序键：按 CCTV-编号 升序，4K/5＋ 紧跟其数字频道之后"""
        n = normalize_channel_name(name)
        m = re.match(r"^CCTV-(\d+)", n)
        if not m:
            return (99, 0, n)
        num = int(m.group(1))
        rest = n[len(m.group(0)):]
        prio = 1 if rest[:1] in ("K", "k", "+", "＋") else 0
        return (num, prio, n)

    def _channel_order_key(self, idx, ch):
        """央视频道整体前置并按编号排序；其余频道保持原始顺序"""
        name = ch.get("channelName", "") if isinstance(ch, dict) else ""
        if categorize_channel(name) == "央视频道":
            return (0, *self._cctv_sort_key(name), idx)
        return (1, 0, 0, "", idx)

    def build(self, channels, channel_infos):
        lines = [f'#EXTM3U x-tvg-url="{constants.EPG_URL}"']
        if not channels:
            return "\n".join(lines)
        if not channel_infos:
            channel_infos = {}

        channels = sorted(
            enumerate(channels),
            key=lambda i_ch: self._channel_order_key(i_ch[0], i_ch[1]),
        )
        channels = [ch for _, ch in channels]

        for ch in channels:
            if not ch or not isinstance(ch, dict):
                continue

            #cat = ch.get("category", "")
            #if cat == "全部":
                #continue

            cid = ch.get("channelID")
            name = ch.get("channelName", "")
            if not name:
                continue

            norm = normalize_channel_name(name)
            group = categorize_channel(name)
            logo = self.build_logo(name)

            info = channel_infos.get(cid) or {}
            if not isinstance(info, dict):
                info = {}

            live = self.build_live_url(
                info.get("channel_url", ""),
                info.get("fcc_ip", ""),
                info.get("fcc_port", ""),
            )
            catchup = self.build_catchup_source(info.get("timeshift_url", ""))

            ext = (f'#EXTINF:-1 tvg-id="{norm}" tvg-name="{norm}" '
                   f'tvg-logo="{logo}" group-title="{group}"')
            if catchup:
                ext += f' catchup="default" catchup-source="{catchup}"'
            ext += f' ,{norm}'
            lines.append(ext)
            if live:
                lines.append(live)

        return "\n".join(lines)

    def save(self, channels, channel_infos):
        try:
            os.makedirs(constants.OUTPUT_DIR, exist_ok=True)
            p = os.path.join(constants.OUTPUT_DIR, "playlist.m3u")
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(self.build(channels, channel_infos))
            os.replace(tmp, p)
            self.logger.info(f"保存: {p}")
            return p
        except Exception as e:
            self.logger.error(f"M3U 保存失败: {e}", exc_info=True)
            return None