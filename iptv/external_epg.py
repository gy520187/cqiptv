# iptv/external_epg.py
import gzip
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from . import constants
from .utils import normalize_channel_name


class ExternalEPG:
    """第三方 XMLTV EPG 源：用于补充运营商无节目数据的频道（运营商数据优先）。"""

    def __init__(self, cfg, logger, url=None):
        self.cfg = cfg
        self.logger = logger
        self.url = url or constants.EXTERNAL_EPG_URL
        self._urls = [u.strip() for u in str(self.url).split(",") if u.strip()]
        self._by_name = {}

    @staticmethod
    def _fmt14(s):
        """XMLTV start/stop -> 北京时间 14 位字符串（统一 +0800 本地时区）"""
        if not s:
            return ""
        m = re.match(r"^(\d{14})(?:\s*([+-]\d{4}))?", str(s).strip())
        if not m:
            return ""
        dt = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
        tz = m.group(2)
        if tz:
            sign = 1 if tz[0] == "+" else -1
            off = timedelta(minutes=sign * (int(tz[1:3]) * 60 + int(tz[3:5])))
            dt = dt - off + timedelta(hours=8)
        return dt.strftime("%Y%m%d%H%M%S")

    def load(self):
        loaded = 0
        for url in self._urls:
            if self._load_one(url):
                loaded += 1
        if loaded:
            self.logger.info(f"外部 EPG 加载成功: {loaded} 个源, {len(self._by_name)} 个频道")
        return loaded > 0

    def _load_one(self, url):
        if not url:
            return False
        try:
            if url.startswith(("http://", "https://")):
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=constants.EXTERNAL_EPG_TIMEOUT) as resp:
                    data = resp.read()
            else:
                with open(url, "rb") as f:
                    data = f.read()
            if data[:2] == b"\x1f\x8b":
                xml = gzip.decompress(data).decode("utf-8", errors="replace")
            else:
                xml = data.decode("utf-8", errors="replace")
            by_name = self._parse(xml)
            # 先到先得：后续源只补充首个源没有的频道
            added = 0
            for name, progs in by_name.items():
                if name not in self._by_name:
                    self._by_name[name] = progs
                    added += 1
            self.logger.info(f"外部 EPG 源 {url}: {len(by_name)} 个频道, 新增 {added}")
            return True
        except Exception as e:
            self.logger.error(f"外部 EPG 源 {url} 加载失败: {e}")
            return False

    def _parse(self, xml):
        root = ET.fromstring(xml)
        chans = {}
        for ch in root.findall("channel"):
            cid = ch.get("id")
            names = [d.text or "" for d in ch.findall("display-name")]
            if cid and names:
                chans[cid] = names[0]

        by_name = {}
        for pr in root.findall("programme"):
            cid = pr.get("channel")
            name = chans.get(cid)
            if not name:
                continue
            title_el = pr.find("title")
            if title_el is None or not title_el.text:
                continue
            item = {
                "beginTimeFormat": self._fmt14(pr.get("start")),
                "endTimeFormat": self._fmt14(pr.get("stop")),
                "programName": title_el.text,
            }
            ep = pr.find("episode-num")
            if ep is not None and ep.text:
                item["contentId"] = ep.text
            by_name.setdefault(name, []).append(item)

        for name in by_name:
            by_name[name].sort(key=lambda x: x.get("beginTimeFormat", ""))
        return by_name

    def get_programs(self, channel_name):
        """按频道名查找外部节目；精确匹配优先，其次双向包含匹配（如 求索 -> 求索记录）"""
        n = normalize_channel_name(channel_name)
        if not n:
            return []
        if n in self._by_name:
            return self._by_name[n]
        for key, progs in self._by_name.items():
            kn = normalize_channel_name(key)
            if n in kn or kn in n:
                return progs
        return []