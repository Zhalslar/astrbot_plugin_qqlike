
import random

import aiocqhttp
from aiocqhttp import CQHttp

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

from .subscribe import SubscribeManager


class LikeExecutor:
    def __init__(
        self,
        config: AstrBotConfig,
        client: CQHttp,
        subscribe_mgr: SubscribeManager,
    ):
        self.conf = config
        self.client = client
        self.subs = subscribe_mgr

    async def like(self, user_id: int | str):
        try:
            times = self.conf["per_like_times"]
            await self.client.send_like(user_id=int(user_id), times=times)
            self.subs.increase(str(user_id), times)
            return True, times, "点赞成功"
        except aiocqhttp.exceptions.ActionFailed as e:
            logger.error(f"给用户 {user_id} 点赞时出现错误: {e}")
            return False, 0, str(e)

    async def like_random(self) -> None:
        """随机给最多 20 位订阅者点赞"""
        users = self.subs.all_user_ids()
        if not users:
            return

        for uid in random.sample(users, min(20, len(users))):
            await self.like(uid)


    async def get_self_like_info(self) -> str:
        """获取bot自身点赞列表"""
        data = await self.client.get_profile_like()
        info = []
        user_infos = data.get("favoriteInfo", {}).get("userInfos", [])
        for user in user_infos:
            if (
                "nick" in user
                and user["nick"]
                and "count" in user
                and user["count"] > 0
            ):
                info.append(f"【{user['nick']}】赞了我{user['count']}次")
        if not info:
            info.append("暂无有效的点赞信息")
        return "\n".join(info)
