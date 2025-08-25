from collections import defaultdict
from typing import List, Dict, Any

from .event_bus import EventBus, BattleEvent
from ..battle.entity import Entity


class BattleSystem:
    def __init__(self):
        self.event_bus = EventBus()
        self.units: List[Entity] = []
        self.current_round = 0
        self.is_battle_active = False
        self._register_core_handlers()
        self._event_type_count: Dict[str, Dict[Any, int]] = defaultdict(lambda: defaultdict(int))

    def _register_core_handlers(self):
        """注册核心事件处理器"""
        self.event_bus.subscribe(BattleEvent.ROUND_START, self._handle_round_start)
        self.event_bus.subscribe(BattleEvent.ROUND_END, self._handle_round_end)

    def add_unit(self, unit: Entity):
        """添加战斗单位"""
        self.units.append(unit)

    def start_battle(self):
        """开始战斗"""
        self.is_battle_active = True
        self.current_round = 1

        self.event_bus.publish(BattleEvent.BATTLE_START, {
            'round': self.current_round,
            'units': self.units
        })

        self.start_round()
    def end_battle(self):
        if not self.is_battle_active:
            return
        # 发布战斗结束事件
        winner = [unit for unit in self.units if unit.is_alive][0].name
        end_data = {
                'round': self.current_round,
                'winner': winner,
                'units': self.units
            }

        self.event_bus.publish(BattleEvent.BATTLE_END, end_data)
        print(f"战斗结束！{'平局' if winner is None else winner + '获胜'}")

    def start_round(self):
        """开始新回合"""
        self.event_bus.publish(BattleEvent.ROUND_START, {
            'round': self.current_round
        })

        # 更新所有单位的Buff和冷却
        for unit in self.units:
            unit.update_buffs()
            unit.update_skill_cooldowns()

        self.event_bus.reset_event_counts()

    def end_round(self):
        """结束当前回合"""
        self.event_bus.publish(BattleEvent.ROUND_END, {
            'round': self.current_round
        })

        self.current_round += 1

    def process_attack(self, attacker: Entity, defender: Entity, base_damage=0.0):
        """处理攻击行动"""
        # 攻击前事件
        attack_data = {
            'source': attacker,
            'target': defender,
            'damage': base_damage,
            'damage_type': 'physical',
            'count_dict': self._event_type_count,
            'max_count': 1
        }

        self.event_bus.publish(BattleEvent.BEFORE_ACTION, attack_data)
        self.event_bus.publish(BattleEvent.ATTACK, attack_data)

        # 伤害计算前事件
        self.event_bus.publish(BattleEvent.BEFORE_DAMAGE_CALC, attack_data)
        self.event_bus.publish(BattleEvent.BEFORE_TAKE_DAMAGE, attack_data)

        # 实际造成伤害
        actual_damage = defender.take_damage(attack_data.get("damage"), 'physical', attacker)
        attack_data['actual_damage'] = actual_damage

        # 伤害计算后事件
        self.event_bus.publish(BattleEvent.AFTER_DAMAGE_CALC, attack_data)

        # 攻击后事件
        self.event_bus.publish(BattleEvent.AFTER_ACTION, attack_data)

        # 检查是否触发受伤害事件
        if actual_damage > 0:
            self.event_bus.publish(BattleEvent.AFTER_TAKE_DAMAGE, {
                'source': attacker,
                'target': defender,
                'damage': actual_damage,
                'damage_type': 'physical'
            })

    def check_battle_end(self) -> bool:
        """检查战斗是否结束"""
        alive_units = [unit for unit in self.units if unit.is_alive]
        return len(alive_units) <= 1

    def _handle_round_start(self, event_data: Dict) -> bool:
        """处理回合开始"""
        print(f"第 {event_data['round']} 回合开始!")
        return True

    def _handle_round_end(self, event_data: Dict) -> bool:
        """处理回合结束"""
        print(f"第 {event_data['round']} 回合结束!")
        return True
