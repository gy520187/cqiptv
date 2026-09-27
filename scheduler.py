# scheduler.py
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from iptv.config import load_config
from iptv.logger import setup_logger
from iptv import constants
from main import collect

cfg = load_config("config.yaml")
logger = setup_logger(cfg)


def job():
    logger.info("定时采集开始")
    try:
        collect()
        logger.info("定时采集完成")
    except Exception as e:
        logger.error(f"定时采集失败: {e}")


if __name__ == "__main__":
    if not constants.SCHEDULER_ENABLED:
        logger.info("定时任务已禁用")
        exit(0)
    sched = BlockingScheduler()
    sched.add_job(job, CronTrigger.from_crontab(constants.SCHEDULER_CRON))
    logger.info(f"定时任务启动: {constants.SCHEDULER_CRON}")
    sched.start()