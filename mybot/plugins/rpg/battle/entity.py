# mybot/plugins/rpg/battle/entity.py
from dataclasses import dataclass
from typing import Dict, List, Optional
import random


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
        self._base = {
            "ATK": int(base_stats.get("ATK", 0)),
            "DEF": int(base_stats.get("DEF", 0)),
            "AGI": int(base_stats.get("AGI", 0)),
            "INT": int(base_stats.get("INT", 0)),
            "CRIT": float(base_stats.get("CRIT", 0.0)),  # 0~1
            "MAX_HP": int(base_stats.get("MAX_HP", 1)),
        }
        # 战斗期可变状态
        self._hp = self._base["MAX_HP"]
        self._temp_pct: Dict[str, float] = {}  # 例如 {"AGI": +20.0}
        self.buffs: List[BuffState] = []
        # 编队信息
        self._enemies: List["Entity"] = []
        self._allies: List["Entity"] = []
        self._rng = random.Random()

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

    def take_damage(self, amount: int, source) -> int:
        amt = max(0, int(amount))
        # 简化减伤：用 DEF 线性抵扣。需要时替换为你项目的公式。
        mitigated = max(0, amt - self.stats.DEF)
        before = self._hp
        self._hp = max(0, self._hp - mitigated)
        return before - self._hp

    def heal(self, amount: int, source):
        self._hp = min(self._base["MAX_HP"], self._hp + max(0, int(amount)))

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
        return self._hp > 0

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
