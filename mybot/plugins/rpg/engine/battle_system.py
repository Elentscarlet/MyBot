import queue
import random
import time
from collections import defaultdict
from typing import List, Dict, Any

from .event_bus import EventBus, BattleEvent
from ..battle.entity import Entity
from ..battle.event_info import EventInfo
from ..util.event_chain_tracker import EventChainTracker


class BattleSystem:
    def __init__(self):
        self.event_bus = EventBus()
        self.units: List[Entity] = []
        self.current_round = 0
        self.is_battle_active = False
        self._register_core_handlers()
        self._event_type_count: Dict[str, Dict[Any, int]] = defaultdict(lambda: defaultdict(int))
        self.winner = None
        self.battle_log = []
        self.event_queue = queue.Queue()
        self.event_tracker = EventChainTracker()  # 初始化事件追踪器
        self.report_mode = 0

    def put_event(self, event: EventInfo):
        self.event_queue.put(event)

    def pop_event(self) -> EventInfo:
        return self.event_queue.get()

    def _register_core_handlers(self):
        """注册核心事件处理器"""
        self.event_bus.subscribe(BattleEvent.ROUND_START, self._handle_round_start)
        self.event_bus.subscribe(BattleEvent.ROUND_END, self._handle_round_end)

    def add_unit(self, unit: Entity):
        """添加战斗单位"""
        self.units.append(unit)

    def start_battle(self, ent_a, ent_b, max_turns: int):
        """开始战斗"""
        self.is_battle_active = True
        self.current_round = 1

        self.event_bus.publish(BattleEvent.BATTLE_START, EventInfo(source=None, target=None))

        self.battle_log.append("\n=== 战斗开始 ===")
        if self.report_mode == 0:
            self.battle_log.append("目前为[完整战报]模式")
        if self.report_mode == 1:
            self.battle_log.append("目前为[精简战报]模式")
        if self.report_mode == 2:
            self.battle_log.append("目前为[无战报]模式")
        # 根据先攻决定攻击者
        first, second = ent_a, ent_b
        attacker, defender = (first, second) if self._get_initiative(first, second) else (second, first)
        for turn in range(1, max_turns + 1):
            if not self.is_battle_active:
                break
            self.start_round()

            # 处理攻击
            self.process_attack(attacker, defender, turn)

            # 交換順序
            attacker, defender = defender, attacker

            self.end_round()

        self.end_battle()

    def _get_initiative(self, ent_a: Entity, ent_b: Entity):
        if ent_a.AGI == ent_b.AGI:
            return random.random() < 0.5  # 50% chance of True/False
        return ent_a.AGI > ent_b.AGI

    def end_battle(self):
        if not self.is_battle_active:
            return
        # 发布战斗结束事件
        print(self.units)
        alive = [unit for unit in self.units if unit.is_alive]

        # 如果没有存活单位，平局
        if not alive:
            self.is_battle_active = False
            self.winner = None
            self.event_bus.publish(BattleEvent.BATTLE_END, EventInfo(source=None, target=None))
            self.battle_log.append("战斗结束！平局")
            self.is_battle_active = False
            return

        # 如果只有一个存活单位，该单位获胜
        if len(alive) == 1:
            winner = alive[0].name
        else:
            # 有多个存活者时，选择血量最多的单位作为获胜者
            # 如果有多个单位血量相同，选择第一个找到的
            winner = max(alive, key=lambda unit: unit.HP).name

        self.winner = winner
        self.event_bus.publish(BattleEvent.BATTLE_END, EventInfo(source=None, target=None))
        self.battle_log.append(f"战斗结束！{winner}获胜")
        self.is_battle_active = False

    def start_round(self):
        """开始新回合"""
        self.event_bus.publish(BattleEvent.ROUND_START,
                               EventInfo(source=None, target=None, round_num=self.current_round))

        # 更新所有单位的Buff和冷却
        for unit in self.units:
            unit.update_buffs()
            unit.update_skill_cooldowns()

        self.event_bus.reset_event_counts()

    def end_round(self):
        """结束当前回合"""
        self.event_bus.publish(BattleEvent.ROUND_END, EventInfo(source=None, target=None, round_num=self.current_round))

        self.current_round += 1

    def process_attack(self, attacker: Entity, defender: Entity, round_num, report_model: int = 0):
        """处理攻击行动"""
        # 创建事件
        attack_data = EventInfo(attacker, defender, is_crit=False,
                                round_num=round_num, can_reflect=True, count_dict=self._event_type_count)

        self.event_bus.publish(BattleEvent.ATTACK, attack_data)
        chain_id = self.event_tracker.start_new_chain(attack_data)

        for e in attack_data.sub_event:
            self.put_event(e)
            self.event_tracker.add_event_to_chain(e, attack_data.event_id)

        processed_events = 0
        max_events = 20  # 防止无限循环
        # 伤害事件循环
        while self.event_queue.qsize() > 0 and processed_events < max_events:
            event = self.pop_event()
            processed_events += 1
            self.event_tracker.add_event_to_chain(event, getattr(event, 'parent_event_id', None))
            # 伤害计算
            self.event_bus.publish(BattleEvent.DAMAGE_CALC, event)

            # 处理伤害
            self._handle_take_damage(event)

            # 伤害结算后
            self.event_bus.publish(BattleEvent.AFTER_TAKE_DAMAGE, event)

            # 日志记录
            # self.event_bus.publish(BattleEvent.AFTER_ACTION, event)

            for e in event.sub_event:
                self.put_event(e)
                self.event_tracker.add_event_to_chain(e, event.event_id)
        # 可选：可视化事件链
        res = ""
        if self.report_mode == 0:
            res = self.visualize_event_chain(chain_id, 10)
        elif self.report_mode == 1:
            res = self.visualize_event_chain(chain_id, 2)
        elif self.report_mode == 2:
            res = ""

        for re in res:
            self.battle_log.append(re)

    def check_battle_end(self) -> bool:
        """检查战斗是否结束"""
        alive_units = [unit for unit in self.units if unit.is_alive]
        return len(alive_units) <= 1

    def _handle_round_start(self, event_data: EventInfo) -> bool:
        """处理回合开始"""
        if self.report_mode != 2:
            self.battle_log.append(f"第 {event_data.round_num} 回合开始!")
        return True

    def _handle_round_end(self, event_data: EventInfo) -> bool:
        """处理回合结束"""
        hp_log = ""
        for unit in self.units:
            hp_log += f"{unit.name}:剩余[{int(unit.HP)}]HP "
        if self.report_mode != 2:
            self.battle_log.append(hp_log)
        if self.check_battle_end():
            self.end_battle()
        return True

    def _handle_take_damage(self, event_data: EventInfo):

        dmg_dict = defaultdict(int)
        dmg_dict[event_data.damage_type] += event_data.amount
        for k, v in event_data.amount_dict.items():
            dmg_dict[k] += v

        if event_data.op == ("damage" or "reflect_damage"):
            event_data.last_amount = 0
            event_data.last_amount = event_data.target.take_damage(dmg_dict)

    def visualize_event_chain(self, chain_id: str, max_depth):
        """可视化事件链"""
        chain = self.event_tracker.get_event_chain(chain_id)
        if not chain:
            print("事件链不存在")
            return

        # 使用DFS遍历事件树
        def dfs(event_id: str, depth: int = 0, prefix: str = "", is_last: bool = True):
            event = self.event_tracker.get_event_by_id(event_id)
            log = []
            if not event:
                return None
            # 构建连接线
            connector = "└── " if is_last else "├── "
            if depth == 0:
                connector = ""  # 根节点不需要连接线
            if depth == max_depth:
                return ""

            # 显示事件信息
            if event.skill:
                amount = event.last_amount if event.last_amount is not None else event.amount

                if event.op == "damage_reduction":
                    event_info = f"{event.source.name} [{event.skill.name}]-> {event.target.name} [减免({amount})点伤害]"
                elif event.op == 'reflect_damage':
                    event_info = f"{event.source.name} [{event.skill.name}]-> {event.target.name} [反射({amount})点伤害]"
                elif event.op == 'damage':
                    event_info = f"{event.source.name} [{event.skill.name}]-> {event.target.name} [造成({amount})点伤害]"
                elif event.op == 'add_damage':
                    event_info = f"{event.source.name} [{event.skill.name}]-> {event.target.name} [附加({amount})点伤害]"
                elif event.op == 'leech':
                    event_info = f"{event.source.name} [{event.skill.name}]-> {event.target.name} [吸收({amount})点生命值]"
                elif event.op == 'heal':
                    event_info = f"{event.source.name} [{event.skill.name}]-> {event.target.name} [恢复({amount})点生命值]"
                else:
                    event_info = f"{event.source.name} [{event.skill.name}]-> {event.target.name} [({amount})]"
                log.append(f"{prefix}{connector}{event_info}")
            else:
                # 对于没有技能的事件（如根事件）
                # event_info = f"{event.source.name} -> {event.target.name}"
                # log.append(f"{prefix}{connector}{event_info}")
                pass

            # 处理子事件
            children = self.event_tracker.get_event_children(event_id)
            for i, child in enumerate(children):
                is_last_child = i == len(children) - 1
                new_prefix = prefix + ("    " if is_last else "│   ")
                res = (dfs(child.event_id, depth + 1, new_prefix, is_last_child))
                for re in res:
                    log.append(re)
            return log

        # 从根事件开始遍历
        return dfs(chain['root_event'].event_id, is_last=True)
