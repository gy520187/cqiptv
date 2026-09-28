# scheduler.py
import time
from datetime import datetime
from apscheduler.triggers.cron import CronTrigger
from iptv.config import load_config
from iptv.logger import setup_logger
from iptv import constants
from main import collect

cfg = load_config("config.yaml")
logger = setup_logger(cfg)


def _load_jobs():
    """读取所有启用的 cron 表达式列表（兼容旧版单任务字段）"""
    raw = cfg.get("scheduler_jobs", None)
    jobs = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("enabled"):
                cron = str(item.get("cron", "") or "").strip()
                if cron:
                    jobs.append(cron)
    if not jobs:
        enabled_raw = cfg.get("scheduler_enabled", "")
        enabled = (str(enabled_raw).lower() in ("1", "true", "yes", "on")
                   if enabled_raw != "" else constants.SCHEDULER_ENABLED)
        cron = cfg.get("scheduler_cron", "") or constants.SCHEDULER_CRON
        if enabled and cron:
            jobs.append(cron)
    return jobs


def _next_run(cron, now=None):
    try:
        trigger = CronTrigger.from_crontab(cron)
        return trigger.get_next_fire_time(None, now or datetime.now())
    except Exception:
        return None


def _next_run_multi(jobs, now=None):
    best = None
    for cron in jobs:
        nr = _next_run(cron, now)
        if nr and (best is None or nr < best):
            best = nr
    return best


def job():
    logger.info("定时采集开始")
    try:
        collect()
        logger.info("定时采集完成")
    except Exception as e:
        logger.error(f"定时采集失败: {e}")


def main_loop():
    while True:
        cfg.load()
        jobs = _load_jobs()
        if not jobs:
            time.sleep(60)
            continue
        nr = _next_run_multi(jobs)
        if nr is None:
            logger.error(f"定时任务 cron 均无效: {jobs}")
            time.sleep(60)
            continue
        for cron in jobs:
            t = _next_run(cron)
            if t:
                logger.info(f"  任务 cron={cron} 下次运行 {t.strftime('%Y-%m-%d %H:%M:%S')}")
        delta = (nr - datetime.now()).total_seconds()
        logger.info(f"最近触发: {nr.strftime('%Y-%m-%d %H:%M:%S')}（{delta:.0f} 秒后）")
        if delta > 60:
            time.sleep(60)
            continue
        time.sleep(max(delta, 1))
        cfg.load()
        jobs = _load_jobs()
        if not jobs:
            continue
        now = datetime.now()
        for cron in jobs:
            t = _next_run(cron, now)
            if t and t <= now:
                job()
                break
        time.sleep(2)


if __name__ == "__main__":
    logger.info("定时任务启动（多任务循环调度，配置热更新）")
    main_loop()