import random
import zoneinfo
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from astrbot.api import logger


class DailyRandomTimeScheduler:
    """
    每天 00:00 刷新一次，在当天随机时间执行一次任务的定时器。

    特性：
    - 时区安全
    - 任务幂等（每天只会执行一次）
    - 仅依赖 async callable，方便跨项目复用
    """

    def __init__(
        self,
        task: Callable[[], Awaitable[None]],
        *,
        job_prefix: str = "DailyRandomTask",
        timezone: str = "Asia/Shanghai",
    ) -> None:
        self._task = task
        self._job_prefix = job_prefix
        self._timezone = zoneinfo.ZoneInfo(timezone)

        self._scheduler = AsyncIOScheduler(timezone=self._timezone)
        self._scheduler.start()

        self._schedule_next_daily_refresh()

    def _schedule_next_daily_refresh(self) -> None:
        """安排下一次 00:00 的刷新任务"""
        now = datetime.now(self._timezone)
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        self._scheduler.add_job(
            func=self._refresh_today_task,
            trigger=DateTrigger(run_date=next_midnight),
            id=f"{self._job_prefix}:daily_refresh:{int(next_midnight.timestamp())}",
            replace_existing=True,
            max_instances=1,
        )

        logger.debug(
            f"[{self._job_prefix}] 已安排下次刷新时间：{next_midnight}",
        )

    def _refresh_today_task(self) -> None:
        """
        随机生成今天的执行时间，并安排一次性任务
        """
        now = datetime.now(self._timezone)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

        if now >= today_end:
            logger.warning(f"[{self._job_prefix}] 今日已结束，跳过任务安排")
            self._schedule_next_daily_refresh()
            return

        seconds_range = int((today_end - now).total_seconds())
        offset_seconds = random.randint(0, seconds_range)
        run_at = now + timedelta(seconds=offset_seconds)

        logger.info(f"[{self._job_prefix}] 今日任务执行时间已随机生成：{run_at}")

        self._scheduler.add_job(
            func=self._run_task_safe,
            trigger=DateTrigger(run_date=run_at),
            id=f"{self._job_prefix}:once:{int(run_at.timestamp())}",
            replace_existing=True,
            max_instances=1,
        )

        # 预先安排下一天的刷新
        self._schedule_next_daily_refresh()

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
