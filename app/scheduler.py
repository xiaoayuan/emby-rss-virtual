import os
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "Asia/Shanghai"))


def _cron_parts(expr: str):
    parts = (expr or "").split()
    if len(parts) != 5:
        parts = ["30", "3", "*", "*", "*"]
    return parts


def apply_schedule(job_func, cron_expr: str):
    minute, hour, day, month, dow = _cron_parts(cron_expr)
    scheduler.add_job(
        job_func,
        "cron",
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=dow,
        id="daily-refresh",
        replace_existing=True,
    )


def start_scheduler(job_func, cron_expr: str):
    apply_schedule(job_func, cron_expr)
    if not scheduler.running:
        scheduler.start()
