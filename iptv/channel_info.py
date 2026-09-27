# iptv/channel_info.py
import re


class ChannelInfoParser:
    def __init__(self, logger):
        self.logger = logger

    def parse(self, html):
        result = {}
        pattern = re.compile(r"CTCSetConfig\('Channel',\s*'([^']+)'\)")
        for m in pattern.finditer(html):
            conf = m.group(1)
            cid = self._extract(conf, "ChannelID")
            if not cid:
                continue
            result[cid] = {
                "channel_name": self._extract(conf, "ChannelName"),
                "user_channel_id": self._extract(conf, "UserChannelID"),
                "timeshift": self._extract(conf, "TimeShift"),
                "channel_url": self._extract(conf, "ChannelURL"),
                "timeshift_url": self._extract(conf, "TimeShiftURL"),
                "fcc_ip": self._extract(conf, "ChannelFCCIP"),
                "fcc_port": self._extract(conf, "ChannelFCCPort"),
            }
        self.logger.info(f"解析 {len(result)} 个频道地址")
        return result

    def _extract(self, conf, key):
        m = re.search(rf'{key}="([^"]*)"', conf)
        return m.group(1) if m else ""