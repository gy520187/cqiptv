# iptv/http_client.py
import time
import requests
from . import constants


class HttpClient:
    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.logger = logger
        # ★ 全局唯一的 session（cookies 自动管理，认证后共享给后续请求）
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; U; Linux i686) AppleWebKit/534.0",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,en-US;q=0.8",
            "Accept-Encoding": "deflate, gzip",
        })

    def url(self, path):
        base = self.cfg.auth_ip or constants.DEFAULT_EPG_BASE
        # 如果 auth_ip 是 http://172.23.88.159:33200/EPG/jsp，会拼成 .../EPG/jsp/xxx
        return base.rstrip("/") + path

    def get(self, path, params=None, referer="", full_url=False):
        url = path if full_url else self.url(path)
        headers = {"Referer": referer} if referer else {}
        for attempt in range(constants.RETRY):
            try:
                r = self.session.get(url, params=params, headers=headers,
                                     timeout=constants.TIMEOUT)
                if r.status_code == 200:
                    return r.text
                self.logger.warning(f"HTTP {r.status_code}: {url}")
            except Exception as e:
                self.logger.warning(f"请求失败({attempt+1}/{constants.RETRY}): {e}")
                time.sleep(1)
        return None

    def post(self, path, data, referer=""):
        url = self.url(path)
        headers = {"Referer": referer} if referer else {}
        try:
            r = self.session.post(url, data=data, headers=headers,
                                  timeout=constants.TIMEOUT)
            return r.text if r.status_code == 200 else None
        except Exception as e:
            self.logger.error(f"POST失败: {e}")
            return None