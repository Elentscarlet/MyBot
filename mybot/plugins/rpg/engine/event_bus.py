from collections import defaultdict
from typing import Dict, List, Any, Callable, Optional

from mybot.plugins.rpg.battle.event_info import EventInfo
from mybot.plugins.rpg.util.config_loader import ConfigLoader


class EventBus:
    config_loader = ConfigLoader()
    def __init__(self):
        self._listeners: Dict[str, List[tuple]] = {}
        self._event_type_count: Dict[str, Dict[Any, int]] = defaultdict(lambda: defaultdict(int))

    def subscribe(self, event_type: str, listener: Callable, priority: int = 0) -> None:
        """订阅事件"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append((listener, priority))
        # 按优先级排序
        self._listeners[event_type].sort(key=lambda x: x[1], reverse=True)

    def unsubscribe(self, event_type: str, listener: Callable) -> None:
        """取消订阅"""
        if event_type in self._listeners:
            self._listeners[event_type] = [
                (l, p) for l, p in self._listeners[event_type] if l != listener
            ]

    def publish(self, event_type: str, event_data: EventInfo) -> Optional[bool]:
        """发布事件"""
        if event_type not in self._listeners:
            return None
        # 获取事件源
        event_source = event_data.source

        if event_source and not self._check_event_limit(event_type, event_source, event_data):
            print(f"{event_source.name} 本回合已无法执行 {event_type} 行为")
            return False
        # 复制监听器列表
        listeners = self._listeners[event_type][:]

        for listener, _ in listeners:
            if not self._check_event_limit(event_type, event_source, event_data):
                return False
            # 如果监听器返回False，停止事件传播
            result = listener(event_data)
            if result is not None and event_source:
                self._increment_event_count(event_type, event_source)
            if result is False:
                return False
        return True

    def _check_event_limit(self, event_type: str, owner: Any, event_data: EventInfo) -> bool:
        """检查行为次数限制"""
        max_count = self.config_loader.get_event_limit(event_type)
        if not max_count:
            return True
        current_count = self._event_type_count[event_type].get(owner, 0)
        return current_count < max_count

    def _increment_event_count(self, event_type: str, owner: Any):
        """增加行为计数"""
        self._event_type_count[event_type][owner] += 1

    def get_event_count(self, event_type: str, owner: Any) -> int:
        """获取指定单位和事件类型的执行次数"""
        return self._event_type_count[event_type].get(owner, 0)

    def reset_event_counts(self):
        """重置所有行为计数"""
        self._event_type_count.clear()

# 事件类型定义
class BattleEvent:
    # 战斗阶段事件
    BATTLE_START = "battle_start"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    BATTLE_END = "battle_end"

    # 单位行动事件
    BEFORE_ACTION = "before_action"
    AFTER_ACTION = "after_action"
    ATTACK = "attack"
    SKILL_CAST = "skill_cast"

    # 伤害相关事件
    DAMAGE_CALC = "damage_calc"
    AFTER_TAKE_DAMAGE = "after_take_damage"

    # 状态效果事件
    BUFF_APPLY = "buff_apply"
    BUFF_REMOVE = "buff_remove"
    DEBUFF_APPLY = "debuff_apply"
    DEBUFF_REMOVE = "debuff_remove"
    STATUS_EXPIRE = "status_expire"

    # 生命值相关事件
    HP_CHANGE = "hp_change"
    HP_BELOW_THRESHOLD = "hp_below_threshold" # 阈值触发
    DEATH = "death"
    REVIVE = "revive"