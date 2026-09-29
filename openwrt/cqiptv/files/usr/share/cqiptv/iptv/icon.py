# iptv/icon.py
import os
import re
import threading
import urllib.parse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import constants
from .utils import normalize_channel_name
from .icon_alias import get_fanmingming_name


# ★ 用 gh-proxy.com 代理访问 fanmingming 图标
FANMINGMING_BASE = "https://gh-proxy.com/https://raw.githubusercontent.com/fanmingming/live/main/tv/{name}.png"


class IconHandler:
    def __init__(self, cfg, logger):
        self.cfg, self.logger = cfg, logger
        self.icon_dir = constants.ICON_DIR
        os.makedirs(self.icon_dir, exist_ok=True)
        self.stats = {"downloaded": 0, "skipped": 0, "failed": 0, "placeholder": 0}
        self._stats_lock = threading.Lock()

    def _inc(self, key):
        with self._stats_lock:
            self.stats[key] += 1

    def icon_path(self, name):
        n = normalize_channel_name(name)
        n = re.sub(r'[\\/:*?"<>|]', "_", n)
        return os.path.join(self.icon_dir, f"{n}.png")

    def exists(self, name):
        return os.path.exists(self.icon_path(name))

    def download_from_fanmingming(self, name):
        fm = get_fanmingming_name(name)
        for ext in ("png", "jpg"):
            url = FANMINGMING_BASE.format(name=urllib.parse.quote(fm))
            if ext == "jpg":
                url = url.rsplit(".", 1)[0] + ".jpg"
            try:
                r = requests.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0",
                })
                if r.status_code == 200 and len(r.content) > 100:
                    with open(self.icon_path(name), "wb") as f:
                        f.write(r.content)
                    self._inc("downloaded")
                    self.logger.info(f"  下载: {name} → {fm}.{ext}")
                    return True
            except Exception as e:
                self.logger.debug(f"  下载失败 {url}: {e}")
        self._inc("failed")
        return False

    def generate_placeholder(self, name):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return False
        path = self.icon_path(name)
        if os.path.exists(path):
            return True
        try:
            img = Image.new("RGB", (200, 200), (44, 62, 80))
            draw = ImageDraw.Draw(img)
            text = normalize_channel_name(name)
            font = None
            for fp in (
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "C:/Windows/Fonts/msyh.ttc",
            ):
                if os.path.exists(fp):
                    try:
                        font = ImageFont.truetype(fp, 24)
                        break
                    except Exception:
                        pass
            if font is None:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text[:8], font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((200 - w) / 2, (200 - h) / 2), text[:8],
                      fill=(255, 255, 255), font=font)
            img.save(path)
            self._inc("placeholder")
            return True
        except Exception as e:
            self.logger.error(f"  占位图失败 {name}: {e}")
            return False

    def ensure_one(self, name, force=False):
        if not force and self.exists(name):
            self._inc("skipped")
            return True
        if self.download_from_fanmingming(name):
            return True
        return self.generate_placeholder(name)

    def _process_one(self, ch, force):
        """单个频道的图标处理（供线程池调用），返回频道名用于进度日志"""
        if not ch or not isinstance(ch, dict):
            return ""
        name = ch.get("channelName", "")
        if not name:
            return ""
        self.ensure_one(name, force=force)
        return name

    def ensure_all(self, channels, force=False, workers=8):
        if not channels:
            return self.stats
        total = len(channels)
        self.logger.info(f"处理图标 {total} 个（源: gh-proxy.com，{workers} 线程并发）")
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self._process_one, ch, force) for ch in channels]
            for fut in as_completed(futures):
                name = fut.result()
                done += 1
                if done % 10 == 0 or done == 1 or done == total:
                    self.logger.info(f"  [{done}/{total}] {name}")
        self.logger.info(
            f"图标完成: 下载 {self.stats['downloaded']}, "
            f"跳过 {self.stats['skipped']}, 失败 {self.stats['failed']}, "
            f"占位 {self.stats['placeholder']}"
        )
        return self.stats