# iptv/storage.py
import os
import json
import sqlite3
from . import constants


class Storage:
    def __init__(self, cfg, logger):
        self.cfg, self.logger = cfg, logger
        os.makedirs(constants.OUTPUT_DIR, exist_ok=True)

    def save_json(self, name, data):
        p = os.path.join(constants.OUTPUT_DIR, name)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False,
                      indent=2 if constants.OUTPUT_PRETTY else None)
        os.replace(tmp, p)
        self.logger.info(f"保存: {p}")

    def save_sqlite(self, channels, epgs):
        """★ 加防御：channels / epgs / epg / programs / page / pr 都判空"""
        self.logger.info(f">>> save_sqlite 开始")
        self.logger.info(f"    channels 类型={type(channels).__name__}, 长度={len(channels) if channels else 0}")
        self.logger.info(f"    epgs 类型={type(epgs).__name__}, 长度={len(epgs) if epgs else 0}")

        if not channels:
            self.logger.error("channels 为空，跳过 SQLite")
            return
        if not epgs:
            self.logger.error("epgs 为空，跳过 SQLite")
            return

        p = os.path.join(constants.OUTPUT_DIR, "iptv.db")
        conn = sqlite3.connect(p)
        cur = conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS channels (
            channel_index INTEGER PRIMARY KEY,
            channel_id TEXT, channel_name TEXT, mediacode TEXT,
            category TEXT, time_shift INTEGER, is_tvod INTEGER, has_subscrib INTEGER)""")

        cur.execute("""CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT, program_name TEXT, content_id TEXT,
            start_time TEXT, end_time TEXT,
            begin_time_format TEXT, end_time_format TEXT,
            is_playable TEXT,
            UNIQUE(channel_id, content_id, begin_time_format))""")

        # ========== 写 channels ==========
        ch_count = 0
        for ch in channels:
            if not ch or not isinstance(ch, dict):
                self.logger.warning(f"    跳过无效频道: {type(ch)}")
                continue
            try:
                cur.execute("""INSERT OR REPLACE INTO channels
                    (channel_index, channel_id, channel_name, mediacode, category,
                     time_shift, is_tvod, has_subscrib)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (ch.get("channelIndex"), ch.get("channelID"), ch.get("channelName"),
                     ch.get("mediacode", ""), ch.get("category", ""),
                     ch.get("timeShift"), ch.get("isTVOD"), ch.get("hasSubscrib")))
                ch_count += 1
            except Exception as e:
                self.logger.warning(f"    写频道失败 {ch.get('channelName')}: {e}")

        self.logger.info(f"    写入 channels: {ch_count}")

        # ========== 写 programs ==========
        prog_count = 0
        skipped = 0
        for cid, epg in epgs.items():
            # ★ 判空
            if not epg or not isinstance(epg, dict):
                skipped += 1
                continue

            programs = epg.get("programs", [])
            if not programs:
                skipped += 1
                continue

            for page in programs:
                # ★ 判空
                if not page:
                    continue

                for pr in page:
                    # ★ 判空
                    if not pr or not isinstance(pr, dict):
                        continue

                    try:
                        cur.execute("""INSERT OR IGNORE INTO programs
                            (channel_id, program_name, content_id, start_time, end_time,
                             begin_time_format, end_time_format, is_playable)
                            VALUES (?,?,?,?,?,?,?,?)""",
                            (cid,
                             pr.get("programName"),
                             pr.get("contentId"),
                             pr.get("startTime"),
                             pr.get("endTime"),
                             pr.get("beginTimeFormat"),
                             pr.get("endTimeFormat"),
                             pr.get("isPlayable")))
                        prog_count += 1
                    except Exception as e:
                        self.logger.warning(f"    写节目失败 {cid}: {e}")

        self.logger.info(f"    写入 programs: {prog_count}, 跳过空EPG: {skipped}")

        conn.commit()
        conn.close()
        self.logger.info(f"保存: {p}")

    def save(self, channels, epgs):
        """★ 每个模块单独 try/except，一个失败不影响其他"""
        fmt = constants.OUTPUT_FORMAT
        full = []
        for ch in channels:
            if not ch:
                continue
            try:
                full.append({**ch, "epg": epgs.get(ch.get("channelID"), {})})
            except Exception:
                full.append(ch)

        if fmt in ("json", "both"):
            try:
                self.save_json("channels.json", channels)
            except Exception as e:
                self.logger.error(f"保存 channels.json 失败: {e}")

            try:
                self.save_json("epg.json", epgs)
            except Exception as e:
                self.logger.error(f"保存 epg.json 失败: {e}")

            try:
                self.save_json("iptv_full.json", full)
            except Exception as e:
                self.logger.error(f"保存 iptv_full.json 失败: {e}")

        if fmt in ("sqlite", "both"):
            try:
                self.save_sqlite(channels, epgs)
            except Exception as e:
                self.logger.error(f"保存 iptv.db 失败: {e}", exc_info=True)