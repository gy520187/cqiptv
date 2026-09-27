# iptv/key_manager.py
from .authenticator import AuthenticatorBruteforcer, AuthenticatorCrypto
from . import constants


class KeyManager:
    def __init__(self, cfg, logger):
        self.cfg, self.logger = cfg, logger

    def get_or_crack(self, allow_crack=True):
        key = self.cfg.key
        if key:
            self.logger.info(f"使用配置中的 key: {key}")
            if self._verify(key):
                return key
            self.logger.warning("key 校验失败，重新破解")

        auth = self.cfg.authenticator
        if not auth:
            self.logger.error("未配置 Authenticator")
            return None

        if not allow_crack:
            self.logger.error(
                "key 缺失或失效。暴力破解可能耗时数小时，"
                "如需自动破解请加 --crack 参数，或使用 Web 破解页 (/crack)"
            )
            return None

        self.logger.info(f"开始破解 {constants.CRACK_START}~{constants.CRACK_END}")
        bf = AuthenticatorBruteforcer(self.logger)
        results = bf.parallel_brute_force(
            auth,
            start=constants.CRACK_START,
            end=constants.CRACK_END,
            workers=constants.CRACK_WORKERS,
            max_found=constants.CRACK_MAX_FOUND,
        )
        if not results:
            return None

        best = results[0]["key"]
        self.logger.info(f"破解成功: {best}")
        if constants.CRACK_WRITE_BACK:
            self.cfg.set_key(best, write_back=True)
        return best

    def _verify(self, key):
        auth = self.cfg.authenticator
        if not auth:
            return True
        try:
            crypto = AuthenticatorCrypto(key)
            plain = crypto.decrypt(auth)
            return "$" in plain
        except Exception:
            return False

    def decrypt_info(self, key):
        auth = self.cfg.authenticator
        if not auth:
            return {}
        try:
            crypto = AuthenticatorCrypto(key)
            plain = crypto.decrypt(auth)
            return AuthenticatorCrypto.parse_decrypted(plain)
        except Exception as e:
            self.logger.error(f"解密失败: {e}")
            return {}