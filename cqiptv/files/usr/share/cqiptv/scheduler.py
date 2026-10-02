# scheduler.py
import os
import time
from datetime import datetime, timedelta, timezone
from apscheduler.triggers.cron import CronTrigger
from iptv.config import load_config
from iptv.logger import setup_logger
from iptv import constants
from main import collect

# 固定使用北京时间（UTC+8），不依赖系统 /etc/localtime 或 tzlocal：
# OpenWrt 上 tzlocal 可能因缺少时区数据而失败，且 Python 未调用 tzset 时
# TZ 环境变量不会生效，导致 CronTrigger 时区探测异常、cron 被误判无效。
CST = timezone(timedelta(hours=8), name="Asia/Shanghai")

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
        trigger = CronTrigger.from_crontab(cron, timezone=CST)
        start = now if now is not None else datetime.now(CST)
        if start.tzinfo is None:
            start_aware = start.replace(tzinfo=CST)
        else:
            start_aware = start.astimezone(CST)
        nr = trigger.get_next_fire_time(None, start_aware)
        return nr.astimezone(CST) if nr else None
    except Exception:
        return None


def _next_run_multi(jobs, now=None):
    best = None
    for cron in jobs:
        nr = _next_run(cron, now)
        if nr and (best is None or nr < best):
            best = nr
    return best


def _maybe_reload():
    """Web 保存定时任务配置后写入标记文件，检测到则重新加载配置。
    返回 True 表示发生了重新加载。
    任何异常都不能导致进程退出：加载失败也删除标记，避免容器重启循环。"""
    flag = constants.SCHEDULER_RELOAD_FLAG
    if not os.path.exists(flag):
        return False
    try:
        cfg.load()
        logger.info("检测到定时任务配置已更新，已重新加载")
    except Exception as e:
        logger.error(f"重新加载定时任务配置失败: {e}")
    finally:
        try:
            os.remove(flag)
        except OSError:
            pass
    return True


def _log_schedule_status(jobs, nr=None):
    """打印各任务下次运行时间和最近触发时间。
    仅在首次启动、定时任务配置更新、上一定时任务完成后调用。"""
    for cron in jobs:
        t = _next_run(cron)
        if t:
            logger.info(f"  任务 cron={cron} 下次运行 {t.strftime('%Y-%m-%d %H:%M:%S')}")
    if nr is None:
        nr = _next_run_multi(jobs)
    if nr:
        delta = (nr - datetime.now(CST)).total_seconds()
        logger.info(f"最近触发: {nr.strftime('%Y-%m-%d %H:%M:%S')}（{delta:.0f} 秒后）")


def job():
    logger.info("定时采集开始")
    try:
        collect()
        logger.info("定时采集完成")
    except BaseException as e:
        # collect() 内部用 sys.exit 终止（SystemExit 是 BaseException），
        # 若不捕获会导致 scheduler 进程退出、容器重启循环
        logger.error(f"定时采集失败: {e}")


def main_loop():
    cfg.load()
    logger.info("定时任务启动（多任务循环调度，保存配置后自动重新加载）")
    jobs = _load_jobs()
    if jobs:
        _log_schedule_status(jobs)
    while True:
        try:
            if _maybe_reload():
                jobs = _load_jobs()
                if jobs:
                    _log_schedule_status(jobs)
            jobs = _load_jobs()
            if not jobs:
                time.sleep(5)
                continue
            nr = _next_run_multi(jobs)
            if nr is None:
                logger.error(f"定时任务 cron 均无效: {jobs}")
                time.sleep(60)
                continue
            delta = (nr - datetime.now(CST)).total_seconds()
            if delta > 60:
                time.sleep(5)
                continue
            time.sleep(max(delta, 1))
            _maybe_reload()
            jobs = _load_jobs()
            if not jobs:
                continue
            if nr <= datetime.now(CST):
                job()
                _log_schedule_status(jobs)
            time.sleep(2)
        except Exception as e:
            logger.error(f"调度循环异常: {e}", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    logger.info("定时任务启动（多任务循环调度，配置变更后自动重新加载）")
    main_loop()