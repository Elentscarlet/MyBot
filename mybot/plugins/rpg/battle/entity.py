# mybot/plugins/rpg/battle/entity.py
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import random

from mybot.plugins.rpg.battle.event_info import EventInfo


@dataclass
class StatsView:
    ATK: int
    DEF: int
    AGI: int
    INT: int
    CRIT: float
    HP: int
    MAX_HP: int


@dataclass
class BuffState:
    buff_id: str
    stacks: int
    remaining_turns: int


class Entity:
    """战斗期实体：被技能引擎调用的唯一对象类型。"""

    def __init__(self, name: str, base_stats: Dict[str, int | float], tag: str = ""):
        self.name = name
        self.tag = tag  # player/monster/boss等
        # 基础面板（不随战斗变化）
        self.ATK = base_stats["ATK"]
        self.DEF = base_stats["DEF"]
        self.AGI = base_stats["AGI"]
        self.CRIT = base_stats["CRIT"]
        self.MAX_HP = base_stats["MAX_HP"]
        self.HP = base_stats["MAX_HP"]

        # 战斗期可变状态
        self._temp_pct: Dict[str, float] = {}  # 例如 {"AGI": +20.0}
        self.is_alive = True
        self.skills: List[Any] = []
        self.buffs: Dict[str, Any] = {}
        self.debuffs: Dict[str, Any] = {}
        # 编队信息
        self._enemies: List["Entity"] = []
        self._allies: List["Entity"] = []
        self._rng = random.Random()
        # 技能引擎
        self.engine = None

    # ===============适配新系统=============
    def take_damage(self, damage) -> float:
        """受到伤害"""
        if not self.is_alive:
            return 0

        # 计算实际伤害（考虑防御等）
        # 伤害减免率 = DEF / (DEF + 40) * 100%
        damage_reduction = self.DEF / (self.DEF + 40)
        actual_damage = max(0, int(damage * (1 - damage_reduction)))

        self.HP = max(0, self.HP - actual_damage)

        # 检查死亡
        if self.HP <= 0:
            self.is_alive = False
            self.HP = 0

        return actual_damage

    def heal(self, amount: float) -> float:
        """接受治疗"""
        if not self.is_alive:
            return 0

        actual_heal = min(amount, self.MAX_HP - self.HP)
        self.HP += actual_heal

        return actual_heal

    def add_buff(self, buff_id: str, duration: int):
        """添加增益效果"""
        self.buffs[buff_id] = duration

    def add_debuff(self, debuff_id: str, duration: int):
        """添加减益效果"""
        self.debuffs[debuff_id] = duration

    def update_buffs(self):
        """更新Buff持续时间"""
        for buff_id in list(self.buffs.keys()):
            self.buffs[buff_id] -= 1
            if self.buffs[buff_id] <= 0:
                del self.buffs[buff_id]

        for debuff_id in list(self.debuffs.keys()):
            self.debuffs[debuff_id] -= 1
            if self.debuffs[debuff_id] <= 0:
                del self.debuffs[debuff_id]

    def update_skill_cooldowns(self):
        """更新技能冷却"""
        for skill in self.skills:
            if hasattr(skill, 'update_cooldown'):
                skill.update_cooldown()

    def is_skill_ready(self, skill_id: str) -> bool:
        """检查技能是否冷却完成"""
        for skill in self.skills:
            if hasattr(skill, 'id') and skill.id == skill_id:
                return skill.current_cooldown <= 0
        return False

    # ===== 组队/选目标 =====
    def set_enemies(self, enemies: List["Entity"]):
        self._enemies = [e for e in enemies if e is not self]

    def set_allies(self, allies: List["Entity"]):
        self._allies = [a for a in allies if a is not self]

    def list_enemies(self) -> List["Entity"]:
        return [e for e in self._enemies if e.is_alive()]

    def pick_enemy_single(
            self, rng: Optional[random.Random] = None
    ) -> Optional["Entity"]:
        pool = self.list_enemies()
        if not pool:
            return None
        (rng or self._rng).shuffle(pool)
        return pool[0]

    def pick_ally_lowest_hp(self) -> Optional["Entity"]:
        pool = [a for a in self._allies if a.is_alive()]
        if not pool:
            return None
        return min(pool, key=lambda x: x.stats.HP / max(1, x.stats.MAX_HP))

    # ===== 数值/伤害 =====
    def try_crit(self) -> bool:
        return self._rng.random() < self.stats.CRIT

    def cal_damage(self, amount: int) -> int:
        # TODO 后续修改防御力计算公式
        dmg = max(0, amount - int(self._base.get("DEF", 0) * 0.2))
        return dmg

    # ===== 临时加成 & Buff =====
    def add_stat_pct(self, stat: str, value: float):
        key = stat.upper()
        self._temp_pct[key] = self._temp_pct.get(key, 0.0) + float(value)

    def add_buff(self, buff_id: str, stacks: int, source):
        ex = next((b for b in self.buffs if b.buff_id == buff_id), None)
        if ex:
            ex.stacks += int(stacks)
        else:
            self.buffs.append(
                BuffState(buff_id, int(stacks), remaining_turns=1)
            )  # 持续由引擎覆盖

    def remove_buff(self, buff_id: str, reason: str = ""):
        self.buffs = [b for b in self.buffs if b.buff_id != buff_id]

    def dispel(self, count: int = 1, positive: bool = True):
        if count > 0:
            del self.buffs[: min(count, len(self.buffs))]

    # ===== 生命周期 =====
    def is_alive(self) -> bool:
        return self.HP > 0

    @property
    def stats(self) -> StatsView:
        def ap(base, key):
            return int(round(base * (1.0 + self._temp_pct.get(key, 0.0) / 100.0)))

        ATK = ap(self._base["ATK"], "ATK")
        DEF = ap(self._base["DEF"], "DEF")
        AGI = ap(self._base["AGI"], "AGI")
        INT = ap(self._base["INT"], "INT")
        return StatsView(
            ATK=ATK,
            DEF=DEF,
            AGI=AGI,
            INT=INT,
            CRIT=min(1.0, max(0.0, self._base["CRIT"])),
            HP=self._hp,
            MAX_HP=self._base["MAX_HP"],
        )
