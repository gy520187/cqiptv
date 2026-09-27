# iptv/icon.py
import os
import re
import urllib.parse
import requests
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
                    self.stats["downloaded"] += 1
                    self.logger.info(f"  下载: {name} → {fm}.{ext}")
                    return True
            except Exception as e:
                self.logger.debug(f"  下载失败 {url}: {e}")
        self.stats["failed"] += 1
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
            self.stats["placeholder"] += 1
            return True
        except Exception as e:
            self.logger.error(f"  占位图失败 {name}: {e}")
            return False

    def ensure_one(self, name, force=False):
        if not force and self.exists(name):
            self.stats["skipped"] += 1
            return True
        if self.download_from_fanmingming(name):
            return True
        return self.generate_placeholder(name)

    def ensure_all(self, channels, force=False):
        if not channels:
            return self.stats
        total = len(channels)
        self.logger.info(f"处理图标 {total} 个（源: gh-proxy.com）")
        for i, ch in enumerate(channels):
            if not ch or not isinstance(ch, dict):
                continue
            name = ch.get("channelName", "")
            if not name:
                continue
            if (i + 1) % 10 == 0 or i == 0 or i == total - 1:
                self.logger.info(f"  [{i+1}/{total}] {name}")
            self.ensure_one(name, force=force)
        self.logger.info(
            f"图标完成: 下载 {self.stats['downloaded']}, "
            f"跳过 {self.stats['skipped']}, 失败 {self.stats['failed']}, "
            f"占位 {self.stats['placeholder']}"
        )
        return self.stats