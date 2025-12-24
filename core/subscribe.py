from astrbot.core.config.astrbot_config import AstrBotConfig


class SubscribeManager:
    """
    订阅管理器（唯一负责 subscribe_data）
    数据格式：
    [
        {"123456": 10},
        {"987654": 5}
    ]
    """

    def __init__(self, config: AstrBotConfig):
        self._config = config
        self._data: list[dict[str, int]] = config["subscribe_data"]

    # ---------- 查询 ----------

    def has(self, user_id: str) -> bool:
        return any(user_id in item for item in self._data)

    def all_user_ids(self) -> list[str]:
        return [uid for item in self._data for uid in item.keys()]

    def is_empty(self) -> bool:
        return not self._data

    # ---------- 修改 ----------

    def add(self, user_id: str) -> bool:
        """新增订阅，已存在返回 False"""
        if self.has(user_id):
            return False

        self._data.append({user_id: 0})
        self._save()
        return True

    def remove(self, user_id: str) -> bool:
        """移除订阅，成功 True"""
        for item in self._data:
            if user_id in item:
                self._data.remove(item)
                self._save()
                return True
        return False

    def increase(self, user_id: str, count: int) -> None:
        """增加当天点赞次数（不存在则忽略）"""
        for item in self._data:
            if user_id in item:
                item[user_id] += count
                self._save()
                return

    def reset_all(self) -> None:
        """清空当天计数（给定时器用）"""
        for item in self._data:
            for uid in item:
                item[uid] = 0
        self._save()

    # ---------- 内部 ----------

    def _save(self) -> None:
        self._config.save_config()
