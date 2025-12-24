import random

from aiocqhttp import CQHttp

from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.filter.permission import PermissionType

from .core.executor import LikeExecutor
from .core.llm import LLMAction
from .core.scheduler import RandomScheduler
from .core.subscribe import SubscribeManager
from .core.utils import get_ats, is_friend


class QQlikePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config
        # LLM 模块
        self.llm = LLMAction(context, config)
        # 订阅管理器
        self.subs = SubscribeManager(config)
        # 点赞执行器
        self.executor: LikeExecutor | None = None
        # 定时器
        self.scheduler: RandomScheduler | None = None

    # ==================== 生命周期 =====================

    async def _delay_initialize(self, client: CQHttp):
        # 实例化执行器
        if not self.executor:
            self.executor = LikeExecutor(
                config=self.conf,
                client=client,
                subscribe_mgr=self.subs,
            )

        # 实例化定时器
        if not self.scheduler and self.executor and self.conf["auto_like"]:
            self.scheduler = RandomScheduler(
                task=self.executor.like_random,
                job_prefix="AutoLike",
                on_refresh =self.subs.reset_all
            )

    async def terminate(self):
        """插件卸载时"""
        if self.scheduler:
            await self.scheduler.shutdown()

    # ==================== 命令 =====================

    @filter.command("订阅点赞")
    async def subscribe_like(self, event: AiocqhttpMessageEvent):
        """订阅点赞，Bot将每日自动给你点赞"""
        sender_id = event.get_sender_id()
        if self.conf["only_like_friend"] and not await is_friend(event.bot, sender_id):
            yield event.plain_result("你没加我好友，不许订阅")
            return
        if not self.subs.add(sender_id):
            yield event.plain_result("你订阅过了")
            return
        yield event.plain_result("订阅成功！我将每天自动为你点赞")

    @filter.command("取消订阅点赞")
    async def unsubscribe_like(self, event: AiocqhttpMessageEvent):
        """取消订阅点赞"""
        if not self.subs.remove(event.get_sender_id()):
            yield event.plain_result("你还没订阅过")
            return
        yield event.plain_result("已取消订阅！我将不再自动给你点赞")

    @filter.command("订阅点赞列表")
    async def like_list(self, event: AiocqhttpMessageEvent):
        """查看谁订阅了点赞"""
        users = self.subs.all_user_ids()
        if not users:
            yield event.plain_result("暂无订阅用户")
            return
        yield event.plain_result("订阅用户：\n" + "\n".join(users))

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("自身赞")
    async def get_profile_like(self, event: AiocqhttpMessageEvent):
        """获取bot自身点赞列表"""
        if self.executor:
            msg = await self.executor.get_self_like_info()
            url = await self.text_to_image(msg)
            yield event.image_result(url)

    # ===================== 监听 =====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_like(self, event: AiocqhttpMessageEvent):
        """消息入口"""
        # 延迟初始化
        await self._delay_initialize(client=event.bot)
        if not self.executor:
            return

        # 前缀校验
        if self.conf["need_prefix"] and not event.is_at_or_wake_command:
            return

        msg = event.message_str
        sender_id = event.get_sender_id()
        target_id = None
        need_reply = False

        # ---------- 先确定目标 ----------
        if msg.startswith("赞"):
            need_reply = True
            if msg == "赞我":
                target_id = sender_id
            else:
                at_ids = get_ats(event)
                target_id = at_ids[0] if at_ids else None

        elif random.random() < self.conf["random_like_prob"]:
            target_id = sender_id

        # 没有目标，直接结束
        if not target_id:
            return

        # ---------- 统一校验 ----------
        if self.conf["only_like_friend"] and not await is_friend(event.bot, target_id):
            if need_reply:
                msg = await self.llm.reply_stranger(event) or "没好友不赞"
                yield event.plain_result(msg)
            return

        # ---------- 统一执行 ----------
        ok, times, result = await self.executor.like(target_id)
        if not need_reply:
            return
        if ok:
            msg = await self.llm.reply_success(event, times)
        else:
            if "已达" in result:
                msg = await self.llm.reply_limit(event)
            elif "权限" in result:
                msg = await self.llm.reply_permission(event)
            else:
                msg = None
        yield event.plain_result(msg or result)
