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


def _settings():
    enabled_raw = cfg.get("scheduler_enabled", "")
    enabled = (str(enabled_raw).lower() in ("1", "true", "yes", "on")
               if enabled_raw != "" else constants.SCHEDULER_ENABLED)
    cron = cfg.get("scheduler_cron", "") or constants.SCHEDULER_CRON
    return enabled, cron


def _next_run(cron, now=None):
    try:
        trigger = CronTrigger.from_crontab(cron)
        return trigger.get_next_fire_time(None, now or datetime.now())
    except Exception:
        return None


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
        enabled, cron = _settings()
        if not enabled:
            time.sleep(60)
            continue
        nr = _next_run(cron)
        if nr is None:
            logger.error(f"定时任务 cron 无效: {cron}")
            time.sleep(60)
            continue
        delta = (nr - datetime.now()).total_seconds()
        logger.info(f"下次采集: {nr.strftime('%Y-%m-%d %H:%M:%S')} (cron={cron})")
        if delta > 60:
            time.sleep(60)
            continue
        time.sleep(max(delta, 1))
        cfg.load()
        enabled, cron = _settings()
        if enabled:
            job()
        time.sleep(2)


if __name__ == "__main__":
    logger.info("定时任务启动（循环调度，配置热更新）")
    main_loop()