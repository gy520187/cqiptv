# iptv/channel.py
import json
import re
from . import constants
from .utils import clean_channel_name, normalize_channel_name, mask_secret


class ChannelCollector:
    def __init__(self, cfg, http, logger):
        self.cfg, self.http, self.logger = cfg, http, logger

    def fetch(self):
        # ★ 调试：打印当前 session 里的 cookies（脱敏，避免凭据落盘）
        cookies = self.http.session.cookies.get_dict()
        self.logger.info(f"fetch 前 cookies: { {k: mask_secret(v) for k, v in cookies.items()} }")

        self.logger.info("拉取频道列表...")
        params = {
            "varName": "channelData",
            "fileds": "-1",
            "isJson": "-1",
            "isAjax": "1",
            "isCountryChannel": str(constants.IS_COUNTRY_CHANNEL),
            "stbType": self.cfg.stb_type,
        }
        referer = self.http.url("/diyiyingshi/en/channel/channelCore.jsp")
        text = self.http.get(constants.PATH_CHANNEL_LIST, params, referer)

        # ★ 调试：打印响应信息
        if text:
            self.logger.info(f"频道列表响应长度: {len(text)}")
            self.logger.info(f"频道列表响应前 200 字: {text[:200]}")
        else:
            self.logger.error("频道列表响应为空（None）")
            return []

        if not text.strip():
            self.logger.error("频道列表响应为空字符串")
            return []

        try:
            data = json.loads(text)
            total = sum(len(c["chanList"]) for c in data)
            self.logger.info(f"  ✅ 解析成功: {len(data)} 栏目, {total} 频道")
            return data
        except json.JSONDecodeError as e:
            self.logger.error(f"解析失败: {e}")
            self.logger.error(f"响应前 500 字: {text[:500]}")
            return []

    def flatten(self, channels):
        """扁平化 + 清洗频道名"""
        seen = {}
        cleaned = 0
        for cat in channels:
            for ch in cat.get("chanList", []):
                if not isinstance(ch, dict):
                    continue
                idx = ch.get("channelIndex")
                if idx is None:
                    # 运营商数据异常时跳过，避免 KeyError 中断整个采集
                    continue
                if idx not in seen:
                    raw = ch.get("channelName", "")
                    clean = clean_channel_name(raw)
                    if raw != clean:
                        cleaned += 1
                    seen[idx] = {
                        "channelIndex": idx,
                        "channelName": clean,
                        "channelNameRaw": raw,
                        "channelID": ch.get("channelID", ""),
                        "timeShift": ch.get("timeShift"),
                        "isTVOD": ch.get("isTVOD"),
                        "hasSubscrib": ch.get("hasSubscrib"),
                        "category": cat.get("chanName", ""),
                    }
        if cleaned:
            self.logger.info(f"  清洗了 {cleaned} 个频道名")
        result = sorted(seen.values(), key=lambda x: x["channelIndex"])
        self.logger.info(f"  扁平化后 {len(result)} 个唯一频道")
        return result


def is_4k_name(name: str) -> bool:
    n = name.lower()
    return "4k" in n or "超高清" in n


def base_channel_name(name: str) -> str:
    """
    4K/超高清频道的基础频道名（剥离末尾 4K/超高清）。
    运营商把 4K 卫视频道的节目单挂在对应高清频道 ID 下
    （如 北京卫视4K 的 EPG 在 北京卫视(高清)=1490 上），据此跨变体回退。
    """
    n = normalize_channel_name(name)
    return re.sub(r"(?:4[kK]|超高清)+$", "", n).strip()


def build_alias_map(pre_channels, channel_infos):
    """
    构建归一化频道名 -> 备用 channelID 列表（同名高清/SD/4K 变体互为 EPG 备选）。
    数据源取并集:
    - channelList.jsp 全量扁平列表（含被 filter_channels 去重掉的 SD/标清变体）
    - getchannellistHWCTC.jsp 解析结果（含 channelList 不下发的 4K 变体）
    运营商 tVod 数据可能只挂在某个变体 ID 上（实测 云南卫视(高清) 全空、SD 有），
    主 ID 无节目时按此映射回退。
    """
    alias_map = {}

    def add(name, cid):
        n = normalize_channel_name(name or "")
        cid = str(cid) if cid else ""
        if not n or not cid:
            return
        lst = alias_map.setdefault(n, [])
        if cid not in lst:
            lst.append(cid)

    for ch in pre_channels or []:
        add(ch.get("channelName"), ch.get("channelID"))
    for cid, info in (channel_infos or {}).items():
        add(info.get("channel_name"), cid)
    return alias_map


def merge_missing_channels(channels, channel_infos, logger):
    """
    运营商 channelList.jsp 可能未及时包含 getchannellistHWCTC.jsp 下发的频道
    （原始抓包证实 4K 频道仅在 getchannellist 下发；运营商上新频道时 channelList 也可能滞后）。
    将频道列表缺失且有组播/回看地址的频道从 getchannellist 解析结果注入，
    使其参与 EPG 采集、图标、存储与 M3U/XMLTV 输出。
    清洗后同名的只保留 UserChannelID 较小者（如 北京卫视4K. 与 北京卫视4K）。
    """
    if not channel_infos:
        return channels
    existing_ids = {str(c.get("channelID")) for c in channels}
    existing_names = {normalize_channel_name(c.get("channelName", "")) for c in channels}
    candidates = []
    for cid, info in channel_infos.items():
        raw_name = info.get("channel_name", "")
        name = clean_channel_name(raw_name)
        if not name:
            continue
        # 无组播/回看地址的频道无实际播放意义，不注入
        if not (info.get("channel_url") or info.get("timeshift_url")):
            continue
        # 排除名单在 filter_channels 阶段已生效，注入阶段同样拦截（如 江苏晚会4K）
        if raw_name in constants.EXCLUDE_CHANNELS or name in constants.EXCLUDE_CHANNELS:
            continue
        if str(cid) in existing_ids:
            continue
        if normalize_channel_name(name) in existing_names:
            continue
        try:
            idx = int(info.get("user_channel_id") or 9999)
        except ValueError:
            idx = 9999
        candidates.append({
            "channelIndex": idx,
            "channelName": name,
            "channelNameRaw": raw_name,
            "channelID": str(cid),
            "timeShift": info.get("timeshift"),
            "isTVOD": 1,
            "hasSubscrib": 1,
            "category": "新增频道",
        })
    # 同名去重，保留 channelIndex 较小者
    by_name = {}
    for c in sorted(candidates, key=lambda x: x["channelIndex"]):
        by_name.setdefault(normalize_channel_name(c["channelName"]), c)
    added = sorted(by_name.values(), key=lambda x: x["channelIndex"])
    if added:
        logger.info(f"注入 channelList 缺失的频道 {len(added)} 个: "
                    + ", ".join(c["channelName"] for c in added))
    return channels + added