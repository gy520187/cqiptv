# iptv/mediacode.py
import re
import json
from . import constants


class MediacodeCollector:
    def __init__(self, cfg, http, logger):
        self.cfg, self.http, self.logger = cfg, http, logger

    def fetch(self):
        self.logger.info("拉取媒体编码映射...")
        referer = self.http.url("/diyiyingshi/en/channel/channelCore.jsp")
        text = self.http.get(constants.PATH_MEDIACODE, referer=referer)
        if not text:
            self.logger.warning("媒体编码响应为空")
            return {}

        # 提取 channelMediacode 对象
        m = re.search(r"var\s+channelMediacode\s*=\s*(\{.*?\});", text, re.S)
        if not m:
            self.logger.warning("未找到 channelMediacode 对象")
            return {}

        js = m.group(1)

        # 清理 JS 语法，转成标准 JSON
        js = re.sub(r"//[^\n]*", "", js)              # 去行注释
        js = re.sub(r"/\*.*?\*/", "", js, flags=re.S) # 去块注释
        js = re.sub(r",(\s*[}\]])", r"\1", js)        # 去尾随逗号
        js = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', js) # 单引号键 → 双引号
        js = re.sub(r":\s*'([^']*)'", r': "\1"', js)   # 单引号值 → 双引号

        try:
            data = json.loads(js)
            result = {k: v for k, v in data.items() if v}
            self.logger.info(f"  ✅ 媒体编码解析成功: {len(result)} 条")
            return result
        except json.JSONDecodeError as e:
            self.logger.error(f"媒体编码解析失败: {e}")
            self.logger.debug(f"清理后 JSON 前 500 字: {js[:500]}")
            # 兜底：用正则逐条提取
            return self._fallback_parse(text)

    def _fallback_parse(self, text):
        """兜底：正则逐条提取 "key": "value" """
        result = {}
        for m in re.finditer(r'"(\d+)"\s*:\s*"([^"]*)"', text):
            k, v = m.group(1), m.group(2)
            if v:
                result[k] = v
        self.logger.info(f"  ✅ 兜底解析: {len(result)} 条")
        return result