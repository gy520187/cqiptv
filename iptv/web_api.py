# iptv/web_api.py
import os
import json
import threading
from . import constants


class WebAPI:
    ALLOWED_FIELDS = {
        "AuthenticationIP", "UserID", "mac", "STBID",
        "STBType", "STBVersion", "SoftwareVersion", "Authenticator", "key",
    }

    def __init__(self, cfg, logger):
        self.cfg, self.logger = cfg, logger
        self._collect_thread = None
        self._crack_thread = None
        self._collect_progress = {"done": True, "msg": ""}
        self._crack_progress = {"done": True, "msg": "", "current": 0, "total": 0, "found": []}

    def get_status(self):
        out_dir = constants.OUTPUT_DIR
        files = []
        if os.path.exists(out_dir):
            for f in os.listdir(out_dir):
                p = os.path.join(out_dir, f)
                files.append({"name": f, "size": os.path.getsize(p),
                              "mtime": os.path.getmtime(p)})
        files.sort(key=lambda x: x["mtime"], reverse=True)
        channels = self._load_json("channels.json") or []
        epgs = self._load_json("epg.json") or {}
        dates = set()
        for cid, epg in (epgs or {}).items():
            if not isinstance(epg, dict):
                continue
            for page in epg.get("programs", []):
                for p in page or []:
                    t = (p or {}).get("beginTimeFormat", "")
                    if len(t) >= 8:
                        dates.add(t[:8])
        return {
            "channels": len(channels),
            "epg_channels": len(epgs),
            "epg_days": len(dates),
            "key": self.cfg.key or "（未破解）",
            "files": files,
            "collecting": not self._collect_progress["done"],
            "cracking": not self._crack_progress["done"],
        }

    def _load_json(self, name):
        p = os.path.join(constants.OUTPUT_DIR, name)
        if not os.path.exists(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def get_channels(self, page=1, size=50, keyword="", category=""):
        channels = self._load_json("channels.json") or []
        if keyword:
            channels = [c for c in channels if keyword in c.get("channelName", "")]
        if category:
            channels = [c for c in channels if category == c.get("category", "")]
        total = len(channels)
        start = (page - 1) * size
        return {"total": total, "page": page, "size": size,
                "items": channels[start:start + size]}

    def get_epg(self, channel_id):
        epgs = self._load_json("epg.json") or {}
        return epgs.get(channel_id, {})

    def get_config(self):
        return self.cfg.raw

    def save_config(self, data):
        try:
            for k, v in data.items():
                if k in self.ALLOWED_FIELDS:
                    self.cfg.set(k, v)
            self.cfg.save()
            self.logger.info(f"配置已保存: {list(data.keys())}")
            return True, "保存成功"
        except Exception as e:
            return False, str(e)

    def is_first_run(self):
        return self.cfg.is_first_run()

    def test_config(self):
        try:
            import requests
            url = self.cfg.auth_ip or constants.DEFAULT_EPG_BASE
            r = requests.get(url, timeout=5)
            return True, f"连接成功 (HTTP {r.status_code})"
        except Exception as e:
            return False, str(e)

    def start_collect(self):
        if not self._collect_progress["done"]:
            return False
        self._collect_progress = {"done": False, "msg": "启动中..."}
        self._collect_thread = threading.Thread(target=self._do_collect, daemon=True)
        self._collect_thread.start()
        return True

    def _do_collect(self):
        try:
            from main import collect
            self._collect_progress["msg"] = "采集中..."
            collect()
            self._collect_progress = {"done": True, "msg": "完成"}
        except Exception as e:
            self.logger.error(f"采集失败: {e}")
            self._collect_progress = {"done": True, "msg": f"失败: {e}"}

    def get_collect_progress(self):
        return self._collect_progress

    def start_crack(self, start=None, end=None, workers=None):
        if not self._crack_progress["done"]:
            return False
        start = start if start is not None else constants.CRACK_START
        end = end if end is not None else constants.CRACK_END
        workers = workers if workers is not None else constants.CRACK_WORKERS
        self._crack_progress = {
            "done": False, "msg": "启动中...",
            "current": start, "total": end - start, "found": [],
        }
        self._crack_thread = threading.Thread(
            target=self._do_crack, args=(start, end, workers), daemon=True)
        self._crack_thread.start()
        return True

    def _do_crack(self, start, end, workers):
        try:
            from .authenticator import AuthenticatorBruteforcer
            auth = self.cfg.authenticator
            if not auth:
                self._crack_progress = {"done": True, "msg": "未配置 Authenticator"}
                return
            bf = AuthenticatorBruteforcer(self.logger)
            self._crack_progress["msg"] = "破解中..."
            results = bf.parallel_brute_force(
                auth, start=start, end=end, workers=workers,
                max_found=constants.CRACK_MAX_FOUND)
            if results:
                key = results[0]["key"]
                self.cfg.set_key(key, write_back=True)
                self._crack_progress = {
                    "done": True, "msg": f"成功，key={key}",
                    "current": end, "total": end - start,
                    "found": [r["info"] for r in results]}
            else:
                self._crack_progress = {
                    "done": True, "msg": "未找到 key",
                    "current": end, "total": end - start, "found": []}
        except Exception as e:
            self.logger.error(f"破解失败: {e}")
            self._crack_progress = {"done": True, "msg": f"失败: {e}"}

    def get_crack_progress(self):
        return self._crack_progress

    def get_logs(self, lines=200):
        path = os.path.join(constants.LOG_DIR, constants.LOG_FILE)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
        return [l.rstrip() for l in all_lines[-lines:]]