# iptv/epg.py
import json
import os
import shutil
import time
from datetime import datetime, timedelta
from . import constants
from .channel import is_4k_name, base_channel_name
from .utils import normalize_channel_name


def alt_ids_for(channel, alias_map):
    """
    频道 EPG 备用 ID 列表。
    4K/超高清频道优先套用基础(高清)频道 ID——运营商将 4K 卫视频道的
    节目单挂在对应高清频道 ID 下；再附加同名 4K 变体 ID。
    普通频道直接取同名变体 ID。均排除主 ID，保持首次出现顺序。
    """
    name = channel.get("channelName", "")
    n = normalize_channel_name(name)
    alts = []
    if is_4k_name(name):
        base = base_channel_name(name)
        if base and base != n:
            alts.extend(alias_map.get(base, []))
    alts.extend(alias_map.get(n, []))
    primary = str(channel.get("channelID"))
    return [a for a in dict.fromkeys(alts) if a != primary]


class EPGCollector:
    def __init__(self, cfg, http, logger):
        self.cfg, self.http, self.logger = cfg, http, logger

    def _fetch_day(self, channel_id, date_index):
        """
        请求参数与原始抓包 e.txt 的回看节目单请求对齐：
        tVodProgramList.jsp?channelId=&dateIndex=&dateSize=2&tVodNumPerPage=999（无 columnId）
        Referer 指向 channelPlayingList.html
        """
        params = {
            "channelId": channel_id,
            "dateIndex": date_index,
            "dateSize": constants.EPG_DATE_SIZE,
            "tVodNumPerPage": constants.EPG_PER_DAY,
        }
        referer = self.http.url("/diyiyingshi/en/channel/channelPlayingList.html")
        text = self.http.get(constants.PATH_EPG, params, referer)
        if not text:
            return None, []
        try:
            data = json.loads(text)
        except Exception:
            self.logger.debug(f"  dateIndex={date_index} 响应非 JSON，跳过")
            return None, []
        if not isinstance(data, list) or len(data) < 2:
            return None, []
        # 防御性检查：data[0] 应携带日期窗口信息，data[1] 应为节目列表容器
        if not isinstance(data[0], dict) or not isinstance(data[1], dict):
            return None, []
        pages = data[1].get("data", []) or []
        programs = [
            p
            for group in pages
            if isinstance(group, list)
            for p in group
            if isinstance(p, dict)
        ]
        return data[0], programs

    def _day_str(self, offset):
        """dateIndex 偏移对应的实际日期（用于按天缓存文件名）"""
        return (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d")

    def _cache_path(self, channel_id, offset):
        """按日期建立文件夹：data/epg_cache/<日期>/<频道ID>.json"""
        return os.path.join(
            constants.EPG_CACHE_DIR, self._day_str(offset), f"{channel_id}.json")

    def _load_cache(self, channel_id, offset):
        """返回 (info, programs)，缓存缺失或损坏时返回 None"""
        path = self._cache_path(channel_id, offset)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_cache(self, channel_id, offset, info, programs):
        path = self._cache_path(channel_id, offset)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump([info, programs], f, ensure_ascii=False)
        except OSError as e:
            self.logger.warning(f"写入 EPG 缓存失败: {e}")

    def _prune_cache(self):
        """
        过期缓存清理：按日期文件夹分类，只保留历史 EPG_HISTORY_DAYS 天
        到未来 DATE_SIZE-1 天（即本次采集的完整日期窗口），范围外删除。
        """
        try:
            if not os.path.isdir(constants.EPG_CACHE_DIR):
                return
            today = datetime.now().date()
            min_date = today - timedelta(days=constants.EPG_HISTORY_DAYS)
            max_date = today + timedelta(days=constants.DATE_SIZE - 1)
            for name in os.listdir(constants.EPG_CACHE_DIR):
                path = os.path.join(constants.EPG_CACHE_DIR, name)
                if not os.path.isdir(path):
                    continue
                try:
                    d = datetime.strptime(name, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if d < min_date or d > max_date:
                    shutil.rmtree(path, ignore_errors=True)
                    self.logger.info(f"清理过期 EPG 缓存: {name}")
        except OSError as e:
            self.logger.warning(f"清理 EPG 缓存失败: {e}")

    def _fetch_days(self, channel_id, force=False):
        """
        逐天拉取一个频道 ID 的全部节目，按 (起止,标题) 去重。
        每拉取一天立即落盘为单文件；非强制刷新时先检查本地缓存，
        命中则跳过网络请求，仅拉取缺失的天数；force=True 时忽略
        缓存，全量重新请求并覆盖本地缓存。
        dateIndex 范围 -EPG_HISTORY_DAYS..DATE_SIZE-1：负数取历史节目
        （供播放器 catchup 回看定位），0 起为未来节目。
        """
        dates = []
        days = []
        seen = set()
        for day in range(-constants.EPG_HISTORY_DAYS, constants.DATE_SIZE):
            if not force:
                cached = self._load_cache(channel_id, day)
                if cached is not None:
                    info, programs = cached
                else:
                    info, programs = self._fetch_day(channel_id, day)
                    self._save_cache(channel_id, day, info, programs)
                    time.sleep(constants.INTERVAL)
            else:
                info, programs = self._fetch_day(channel_id, day)
                self._save_cache(channel_id, day, info, programs)
                time.sleep(constants.INTERVAL)
            if info and not dates:
                dates = info.get("data", []) or []
            fresh = []
            for p in programs:
                key = (p.get("beginTimeFormat"), p.get("endTimeFormat"), p.get("programName"))
                if key in seen:
                    continue
                seen.add(key)
                fresh.append(p)
            if fresh:
                days.append(fresh)
        return dates, days

    def fetch(self, channel_id, alt_ids=None, force=False):
        """
        运营商接口一次只返回 dateIndex 对应一天的节目单（原始抓包证实：
        dateSize=8 的响应也只有当天 36 条节目），逐天请求拼出多日 EPG。
        同名频道存在高清/SD 等变体时，tVod 数据可能只挂在某个 ID 上
        （实测 云南卫视(高清)=642905769 无数据，SD 变体=1672 有）：
        主 ID 8 天全空则依次回退备用 ID。返回仍按主 channelID 语义使用。
        force=True 时忽略缓存全量刷新。
        """
        dates, days = self._fetch_days(channel_id, force=force)
        if not days and alt_ids:
            for alt in alt_ids:
                self.logger.info(f"    channelId={channel_id} 无节目数据, 回退备用 ID {alt}")
                alt_dates, alt_days = self._fetch_days(alt, force=force)
                if alt_days:
                    dates = alt_dates
                    days = alt_days
                    break
        return {
            "dates": dates,
            "programs": days,
        }

    def fetch_all(self, channels, alias_map=None, force=False):
        alias_map = alias_map or {}
        total = len(channels)
        if constants.MAX_CHANNELS > 0:
            total = min(total, constants.MAX_CHANNELS)
        if force:
            self.logger.info("强制全量刷新模式：忽略本地缓存，重新请求全部日期")
        self.logger.info(
            f"采集节目单，{total} 频道 × "
            f"{constants.EPG_HISTORY_DAYS} 天历史 + {constants.DATE_SIZE} 天未来")

        # 采集前清理过期缓存，只保留历史 7 天到未来 8 天
        self._prune_cache()

        result = {}
        # 并发数 <=1 或频道数 <=1 时退化为串行（保持原行为）
        workers = constants.EPG_WORKERS
        if workers <= 1 or total <= 1:
            for i, ch in enumerate(channels[:total]):
                cid = ch["channelID"]
                self.logger.info(f"  [{i+1}/{total}] {ch['channelName']}")
                epg = self.fetch(cid, alt_ids_for(ch, alias_map), force=force)
                n_days = len(epg["programs"])
                n_progs = sum(len(d) for d in epg["programs"])
                self.logger.info(f"    {n_days} 天 / {n_progs} 条节目")
                result[cid] = epg
                time.sleep(constants.INTERVAL)
            return result

        from concurrent.futures import ThreadPoolExecutor, as_completed

        futures = {}
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="epg") as pool:
            for i, ch in enumerate(channels[:total]):
                cid = ch["channelID"]
                self.logger.info(f"  [{i+1}/{total}] {ch['channelName']}")
                futures[pool.submit(self.fetch, cid, alt_ids_for(ch, alias_map), force)] = (cid, ch)
            done = 0
            for fut in as_completed(futures):
                cid, ch = futures[fut]
                done += 1
                try:
                    epg = fut.result()
                    n_days = len(epg["programs"])
                    n_progs = sum(len(d) for d in epg["programs"])
                    self.logger.info(f"    [{done}/{total}] {ch['channelName']}: {n_days} 天 / {n_progs} 条节目")
                    result[cid] = epg
                except Exception as e:
                    self.logger.error(f"    [{done}/{total}] {ch['channelName']} 采集失败: {e}")
        return result
