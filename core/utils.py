from aiocqhttp import CQHttp

from astrbot.core.message.components import At
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


async def is_friend(client: CQHttp, user_id: int | str) -> bool:
    """判断 user_id 是否为好友"""
    friend_list = await client.get_friend_list()
    friend_ids = [str(f["user_id"]) for f in friend_list]
    print(friend_ids)
    return str(user_id) in friend_ids


def get_ats(event: AiocqhttpMessageEvent) -> list[str]:
    """获取被at者们的id列表,(@增强版)"""
    ats = [str(seg.qq) for seg in event.get_messages()[1:] if isinstance(seg, At)]
    for arg in event.message_str.split(" "):
        if arg.startswith("@") and arg[1:].isdigit():
            ats.append(arg[1:])
    return ats

async def get_nickname(client: CQHttp, group_id: int | str, user_id: int | str) -> str:
    """获取指定群友的群昵称或 Q 名，群接口失败/空结果自动降级到陌生人资料"""
    user_id = int(user_id)
    info = {}
    if str(group_id).isdigit():
        try:
            info = (
                await client.get_group_member_info(
                    group_id=int(group_id), user_id=user_id
                )
                or {}
            )
        except Exception:
            pass
    if not info:
        try:
            info = await client.get_stranger_info(user_id=user_id) or {}
        except Exception:
            pass
    return info.get("card") or info.get("nickname") or info.get("nick") or str(user_id)

