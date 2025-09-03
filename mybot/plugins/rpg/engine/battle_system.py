import queue
import random
from collections import defaultdict
from typing import List, Dict, Any

from .event_bus import EventBus, BattleEvent
from ..battle.entity import Entity
from ..battle.event_info import EventInfo
from ..util.event_chain_tracker import EventChainTracker


def build_log_msg(event: EventInfo):
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
    elif event.op == 'apply_buff':
        event_info = f"{event.source.name} [{event.skill.name}]-> {event.target.name} [{event.additional_msg}]"
    else:
        event_info = f"{event.source.name} [{event.skill.name}]-> {event.target.name} [({amount})]"
    if event.is_dodged:
        event_info += "[🌀闪避!!!]"
    elif event.is_crit:
        event_info += "[💥暴击!!!]"
    return event_info


def _get_initiative(ent_a: Entity, ent_b: Entity):
    if ent_a.AGI == ent_b.AGI:
        return random.random() < 0.5  # 50% chance of True/False
    return ent_a.AGI > ent_b.AGI


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
        self.event_bus.subscribe(BattleEvent.AFTER_ATTACK, self._handle_after_attack)
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
        attacker, defender = (first, second) if _get_initiative(first, second) else (second, first)
        for turn in range(1, max_turns + 1):
            if not self.is_battle_active:
                break
            """开始新回合"""
            # 更新所有单位的Buff和冷却
            for unit in self.units:
                unit.update_buffs()
                unit.update_skill_cooldowns()

            # 创建事件
            round_data = EventInfo(attacker, defender, is_crit=False,
                                   round_num=self.current_round, can_reflect=True,
                                   count_dict=self._event_type_count)
            chain_id = self.event_tracker.start_new_chain(round_data)

            self.event_bus.publish(BattleEvent.ROUND_START, round_data)

            self.event_bus.reset_event_counts()

            # 处理攻击
            self.event_bus.publish(BattleEvent.ATTACK, round_data)

            for e in round_data.sub_event:
                self.put_event(e)
                self.event_tracker.add_event_to_chain(e, round_data.event_id)

            processed_events = 0
            max_events = 20  # 防止无限循环
            # 伤害事件循环
            while self.event_queue.qsize() > 0 and processed_events < max_events:
                event = self.pop_event()
                processed_events += 1
                self.event_tracker.add_event_to_chain(event, event.parent_event_id)

                # 攻击后阶段:闪避计算
                self.event_bus.publish(BattleEvent.AFTER_ATTACK, event)

                # 伤害计算
                self.event_bus.publish(BattleEvent.DAMAGE_CALC, event)

                # 处理伤害
                self._handle_take_damage(event)

                # 伤害结算后
                self.event_bus.publish(BattleEvent.AFTER_TAKE_DAMAGE, event)

                for e in event.sub_event:
                    self.put_event(e)

            # 交換順序
            attacker, defender = defender, attacker

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

            """结束当前回合"""
            self.current_round += 1
            self.event_bus.publish(BattleEvent.ROUND_END,round_data)

        self.end_battle()

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

    def check_battle_end(self) -> bool:
        """检查战斗是否结束"""
        alive_units = [unit for unit in self.units if unit.is_alive]
        return len(alive_units) <= 1

    def _handle_round_start(self, event_data: EventInfo) -> bool:
        """处理回合开始"""
        if self.report_mode != 2:
            self.battle_log.append(f"第 {event_data.round_num} 回合开始!")
        return True

    def _handle_after_attack(self,event_data: EventInfo) -> bool:

        # 闪避判定
        if event_data.can_dodge:
            if event_data.target.check_dodged():
                event_data.is_dodged = True
                event_data.can_reduce = False
                event_data.can_reflect = False
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

        if event_data.is_dodged:
            event_data.last_amount = 0
            return

        dmg_dict = defaultdict(int)
        dmg_dict[event_data.damage_type] += event_data.amount
        for k, v in event_data.amount_dict.items():
            dmg_dict[k] += v

        # 计算伤害
        if event_data.op == "damage" or event_data.op == "reflect_damage":
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
                event_info = build_log_msg(event)
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
