# iptv/config.py
import os
import shutil
from ruamel.yaml import YAML


class Config:
    FIELDS = [
    "AuthenticationIP", "UserID", "mac", "STBID",
    "STBType", "STBVersion", "SoftwareVersion", "Authenticator", "key",
    "ip", "SessionID",
]

    def __init__(self, path="config.yaml"):
        self.path = path
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.raw = {}
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            template = "config.example.yaml"
            if os.path.exists(template):
                shutil.copy(template, self.path)
            else:
                self._create_default()
        with open(self.path, "r", encoding="utf-8") as f:
            self.raw = self.yaml.load(f) or {}
        for f in self.FIELDS:
            self.raw.setdefault(f, "")

    def _create_default(self):
        default = {f: "" for f in self.FIELDS}
        with open(self.path, "w", encoding="utf-8") as f:
            self.yaml.dump(default, f)

    def save(self):
        import glob
        import time
        if os.path.exists(self.path):
            shutil.copy(self.path, f"{self.path}.bak.{int(time.time())}")
            # 备份轮转：只保留最近 5 份
            backups = sorted(glob.glob(f"{self.path}.bak.*"))
            for old in backups[:-5]:
                os.remove(old)
        with open(self.path, "w", encoding="utf-8") as f:
            self.yaml.dump(self.raw, f)

    def get(self, key, default=""):
        v = self.raw.get(key)
        if v is None:
            return default
        return v

    def set(self, key, value, write_back=False):
        self.raw[key] = value
        if write_back:
            self.save()

    # ========== 8 个字段属性 ==========
    @property
    def auth_ip(self):
        return self.get("AuthenticationIP")

    @property
    def user_id(self):
        return self.get("UserID")

    @property
    def mac(self):
        return self.get("mac")

    @property
    def stb_id(self):
        return self.get("STBID")

    @property
    def stb_type(self):
        return self.get("STBType")

    @property
    def stb_version(self):
        return self.get("STBVersion")

    @property
    def software_version(self):
        return self.get("SoftwareVersion")

    @property
    def authenticator(self):
        return self.get("Authenticator")

    @property
    def key(self):
        return self.get("key")
    
    @property
    def ip(self):
        return self.get("ip")

    def set_key(self, key, write_back=True):
        self.set("key", key, write_back=write_back)

    def is_first_run(self) -> bool:
        # ip 为可选项（auth.py 有默认值），不参与必填校验，否则首次配置后仍会重定向到 /setup
        checks = [
            self.get("AuthenticationIP"),
            self.get("UserID"),
            self.get("mac"),
            self.get("STBID"),
            self.get("STBType"),
        ]
        return not all(checks)


def load_config(path="config.yaml") -> Config:
    return Config(path)