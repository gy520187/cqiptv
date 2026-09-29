# iptv/authenticator.py
import time
from typing import Optional, Dict, List

try:
    from Crypto.Cipher import DES          # ← 改成 DES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

from multiprocessing import Pool
from .utils import mask_secret


class AuthenticatorCrypto:
    def __init__(self, key: str = ""):
        if not HAS_CRYPTO:
            raise ImportError("pip install pycryptodome")
        self.mode = DES.MODE_ECB           # ← 改成 DES.MODE_ECB
        if key:
            self.key = self._expand_key(key)
            self.cipher = DES.new(self.key.encode(), self.mode)  # ← 改成 DES.new
        else:
            self.key = None
            self.cipher = None

    @staticmethod
    def _expand_key(key: str) -> str:
        """8 位数字 key → 8 字节 DES 密钥"""
        if len(key) >= 8:
            return key[:8]
        return key.ljust(8, "0")           # ← 补到 8 字节

    @staticmethod
    def _pad(text: str, block_size: int = 8) -> bytes:
        pad_len = block_size - len(text) % block_size
        return (text + chr(pad_len) * pad_len).encode("utf-8")

    @staticmethod
    def _unpad(data: bytes) -> str:
        if not data:
            return ""
        pad = data[-1]
        if 0 < pad <= 8 and data.endswith(bytes([pad]) * pad):
            data = data[:-pad]
        return data.decode("utf-8", errors="ignore")

    def decrypt(self, hex_text: str) -> str:
        cipher_bytes = bytes.fromhex(hex_text)
        plain = self.cipher.decrypt(cipher_bytes)
        return self._unpad(plain)

    def encrypt(self, text: str) -> str:
        padded = self._pad(text)
        return self.cipher.encrypt(padded).hex()

    @staticmethod
    def parse_decrypted(plain_text: str) -> Dict[str, str]:
        parts = plain_text.split("$")
        fields = ["random", "token", "user_id", "stb_id", "ip", "mac", "_", "isp"]
        result = {}
        for i, val in enumerate(parts):
            if i < len(fields):
                result[fields[i]] = val
            else:
                result[f"extra_{i}"] = val
        return result


def _crack_worker(args):
    start, end, authenticator, keywords = args
    import logging
    logger = logging.getLogger("iptv.crack")
    bf = AuthenticatorBruteforcer(logger, keywords)
    return bf.brute_force(authenticator, start=start, end=end,
                          max_found=1, progress_every=100000000)


class AuthenticatorBruteforcer:
    def __init__(self, logger, valid_keywords: Optional[List[str]] = None):
        self.logger = logger
        self.valid_keywords = valid_keywords or ["$", "@itv"]

    def _looks_valid(self, plain: str) -> bool:
        if not plain or len(plain) < 10:
            return False
        for kw in self.valid_keywords:
            if kw not in plain:
                return False
        return True

    def brute_force(self, authenticator, start=0, end=100000000,
                    max_found=20, progress_every=1000000):
        if len(authenticator) < 10:
            return []
        self.logger.info(f"暴力破解 {start:08d}~{end:08d}")
        t0 = time.time()
        found = []
        for x in range(start, end):
            key = f"{x:08d}"
            if x > 0 and x % progress_every == 0:
                self.logger.info(f"  已搜索 {x} ({time.time()-t0:.0f}s)")
            try:
                crypto = AuthenticatorCrypto(key)
                plain = crypto.decrypt(authenticator)
                if self._looks_valid(plain):
                    info = AuthenticatorCrypto.parse_decrypted(plain)
                    self.logger.info(f"  命中 key={mask_secret(key)}")
                    found.append({"key": key, "plain": plain, "info": info})
                    if len(found) >= max_found:
                        break
            except Exception:
                continue
        self.logger.info(f"完成，{len(found)} 个 key，{time.time()-t0:.0f}s")
        return found

    def parallel_brute_force(self, authenticator, start=0, end=100000000,
                             workers=8, max_found=5):
        if workers <= 1:
            return self.brute_force(authenticator, start, end, max_found)
        total = end - start
        chunk = total // workers
        tasks = []
        for i in range(workers):
            s = start + i * chunk
            e = start + (i + 1) * chunk if i < workers - 1 else end
            tasks.append((s, e, authenticator, self.valid_keywords))
        self.logger.info(f"多进程破解：{workers} 进程")
        found = []
        with Pool(workers) as pool:
            for result in pool.imap_unordered(_crack_worker, tasks):
                if result:
                    found.extend(result)
                    if len(found) >= max_found:
                        pool.terminate()
                        break
        return found[:max_found]