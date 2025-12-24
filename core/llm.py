import json

from astrbot.api import logger
from astrbot.api.star import Context
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.db.po import Persona, Personality
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .utils import get_nickname


class LLMAction:
    def __init__(self, context: Context, config: AstrBotConfig):
        self.context = context
        self.conf = config

    async def _get_llm_respond(
        self, event: AiocqhttpMessageEvent, prompt: str
    ) -> str | None:
        """调用 LLM，返回原始文本（不做信任）"""
        umo = event.unified_msg_origin

        conv_mgr = self.context.conversation_manager
        curr_cid = await conv_mgr.get_curr_conversation_id(umo)
        if not curr_cid:
            return None

        conversation = await conv_mgr.get_conversation(umo, curr_cid)
        if not conversation:
            return None

        try:
            contexts = json.loads(conversation.history)
        except Exception:
            contexts = []

        using_provider = self.context.get_using_provider(umo)
        if not using_provider:
            return None

        # system prompt（人格）
        try:
            persona: Persona = await self.context.persona_manager.get_persona(
                persona_id=conversation.persona_id  # type: ignore
            )
            system_prompt = persona.system_prompt
        except Exception:
            personality: Personality = (
                await self.context.persona_manager.get_default_persona_v3(umo=umo)
            )
            system_prompt = personality["prompt"]

        try:
            logger.debug(f"LLM prompt:\n{prompt}")
            resp = await using_provider.text_chat(
                system_prompt=system_prompt,
                prompt=prompt,
                contexts=contexts,
            )
            logger.debug(f"LLM response:\n{resp.completion_text}")
            return resp.completion_text
        except Exception as e:
            logger.error(f"LLM fail：{e}")
            return None

    def _build_prompt(self, style: str, scenario: str) -> str:
        return f"""
你正在用 QQ 和别人聊天，需要给出一句自然的回复。

【硬性规则】
1. 只允许输出 JSON
2. JSON 只能包含一个字段 text
3. 不允许输出解释、注释、Markdown
4. 不允许出现换行符

JSON 格式：
{{"text":"回复内容"}}

【场景】
{scenario}

【回复风格】
{style}
"""

    def _parse_llm_json(self, raw: str | None) -> str | None:
        """内部：唯一可信解析口"""
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                text = data.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        except Exception:
            pass
        return None

    async def reply_success(
        self,
        event: AiocqhttpMessageEvent,
        total_likes: int,
    ) -> str | None:
        """生成点赞成功的回复"""
        username = await get_nickname(
            event.bot, event.get_group_id(), event.get_sender_id()
        )
        scenario = f"你刚刚成功给 {username} 点赞 {total_likes} 次。"

        prompt = self._build_prompt(self.conf["llm_success_style"], scenario)
        raw = await self._get_llm_respond(event, prompt)
        return self._parse_llm_json(raw)

    async def reply_limit(
        self,
        event: AiocqhttpMessageEvent,
    ) -> str | None:
        """生成 点赞达到上限 的回复"""
        username = await get_nickname(
            event.bot, event.get_group_id(), event.get_sender_id()
        )

        scenario = (
            f"{username}想要你的赞，但是今天已经给 {username} 点赞到上限，不能再点了。"
        )

        prompt = self._build_prompt(self.conf["llm_limit_style"], scenario)
        raw = await self._get_llm_respond(event, prompt)
        return self._parse_llm_json(raw)

    async def reply_stranger(
        self,
        event: AiocqhttpMessageEvent,
    ) -> str | None:
        """生成 给陌生人点赞失败 的回复"""
        username = await get_nickname(
            event.bot, event.get_group_id(), event.get_sender_id()
        )
        scenario = f"{username} 想要你赞Ta，但是{username} 不是你的好友，你点不了赞"
        prompt = self._build_prompt(self.conf["llm_stranger_style"], scenario)
        raw = await self._get_llm_respond(event, prompt)
        return self._parse_llm_json(raw)

    async def reply_permission(
        self,
        event: AiocqhttpMessageEvent,
    ) -> str | None:
        """生成 权限限制 的回复"""
        scenario = "对方想让你给Ta点赞，但Ta设了权限不许你这个陌生人赞Ta"

        prompt = self._build_prompt(self.conf["llm_permission_style"], scenario)
        raw = await self._get_llm_respond(event, prompt)
        return self._parse_llm_json(raw)
