import random
import zoneinfo
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from astrbot.api import logger


class RandomScheduler:
    """
    每个周期刷新一次，在当天随机时间执行一次任务的定时器。
    """

    def __init__(
        self,
        task: Callable[[], Awaitable[None]],
        *,
        job_prefix: str = "DailyRandomTask",
        timezone: str = "Asia/Shanghai",
        cron_expr: str = "0 0 * * *",  # 默认是每天 00:00
        on_refresh: Callable[[], None] | None = None,
    ) -> None:
        self._task = task
        self._on_refresh = on_refresh
        self._job_prefix = job_prefix
        self._timezone = zoneinfo.ZoneInfo(timezone)
        self._cron_expr = cron_expr

        self._scheduler = AsyncIOScheduler(timezone=self._timezone)
        self._scheduler.start()

        self._refresh_cycle_task()

    def _schedule_next_refresh(self) -> None:
        """安排下一周期的刷新任务"""
        self._scheduler.add_job(
            func=self._refresh_cycle_task,
            trigger=CronTrigger.from_crontab(self._cron_expr, timezone=self._timezone),
            id=f"{self._job_prefix}:cycle_refresh",
            replace_existing=True,
            max_instances=1,
        )

        logger.debug(
            f"[{self._job_prefix}] 已用 cron「{self._cron_expr}」安排周期刷新",
        )

    def _refresh_cycle_task(self) -> None:
        now = datetime.now(self._timezone)
        cron = CronTrigger.from_crontab(self._cron_expr, timezone=self._timezone)
        next_refresh = cron.get_next_fire_time(None, now)
        if next_refresh is None:
            logger.warning(f"[{self._job_prefix}] 周期表达式无效，跳过")
            return

        seconds_range = int((next_refresh - now).total_seconds())
        if seconds_range <= 0:
            logger.warning(f"[{self._job_prefix}] 周期已结束，跳过")
            self._schedule_next_refresh()
            return

        offset_seconds = random.randint(0, seconds_range)
        run_at = now + timedelta(seconds=offset_seconds)
        logger.info(f"[{self._job_prefix}] 本次周期内任务执行时间已随机生成：{run_at}")

        if self._on_refresh:
           try:
               self._on_refresh()
           except Exception:
               logger.error(f"[{self._job_prefix}] on_refresh 异常，忽略")

        period_id = int(next_refresh.timestamp())
        self._scheduler.add_job(
            func=self._run_task_safe,
            trigger=DateTrigger(run_date=run_at),
            id=f"{self._job_prefix}:once:{period_id}",
            replace_existing=True,
            max_instances=1,
        )

        self._schedule_next_refresh()

    async def _run_task_safe(self) -> None:
        """
        任务安全执行包装器，防止异常导致调度器状态异常
        """
        logger.info(f"[{self._job_prefix}] 开始执行任务")
        try:
            await self._task()
        except Exception:
            logger.exception(f"[{self._job_prefix}] 任务执行异常")
        else:
            logger.info(f"[{self._job_prefix}] 任务执行完成")

    async def shutdown(self) -> None:
        """优雅关闭调度器"""
        self._scheduler.remove_all_jobs()
        self._scheduler.shutdown(wait=False)
        logger.info(f"[{self._job_prefix}] 调度器已停止")
