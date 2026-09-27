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

    def build(self, channels, channel_infos):
        lines = ["#EXTM3U"]
        if not channels:
            return "\n".join(lines)
        if not channel_infos:
            channel_infos = {}

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
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.build(channels, channel_infos))
            self.logger.info(f"保存: {p}")
            return p
        except Exception as e:
            self.logger.error(f"M3U 保存失败: {e}", exc_info=True)
            return None