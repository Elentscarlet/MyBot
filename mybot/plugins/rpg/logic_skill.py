# mybot/plugins/rpg/logic_skill.py
# -*- coding: utf-8 -*-
"""
技能系统与Buff引擎：
- 统一抽象：Skill / Buff / Entity
- 事件驱动：on_battle_start / on_turn_start / on_before_skill / on_deal_damage / on_receive_damage / on_death / on_turn_end / on_battle_end
- Buff 结算：加成(ATK+/ATK% 等)、持续回合、叠层、可驱散
- 示例技能：重击(主动伤害)、迅捷(自Buff)、嗜血(条件被动)、荆棘(反伤被动)、吸血(造成伤害回血)
- 装备函数：根据“武器评分”装配技能集合
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional

# ========= 数据结构 =========


@dataclass
class Buff:
    id: str
    name: str
    effect: Dict[str, float]  # 例如 {"ATK%":0.2, "SPD+":5}
    duration: int  # -1 = 永久（被动/光环）
    stacks: int = 1
    max_stacks: int = 1
    dispellable: bool = True
    hooks: Dict[str, Callable] = field(
        default_factory=dict
    )  # 事件钩子，键为事件名（如'on_turn_start'），值为回调函数（如持续伤害/反击等）


@dataclass
class Skill:
    id: str
    name: str
    type: Literal["active", "passive", "aura"] = "active"
    cd: int = 0
    cost: int = 0  # 资源消耗，可选（怒气/能量）
    target: Literal["enemy", "self", "ally"] = "enemy"
    use: Optional[Callable] = None  # 主动技能具体执行器 use(user, target, engine)
    hooks: Dict[str, Callable] = field(
        default_factory=dict
    )  # 被动技能事件钩子，键为事件名（如'on_turn_start'），值为回调函数
    use: Optional[Callable[[Entity, Entity, "SkillEngine"], None]] = (
        None  # 主动技能具体执行器 use(user: Entity, target: Entity, engine: SkillEngine) -> None
    )


@dataclass
class Entity:
    name: str
    base: Dict[str, float]  # ATK/DEF/HP/SPD/CRIT
    hp: int
    buffs: List[Buff] = field(default_factory=list)  # Buff 实例列表
    cds: Dict[str, int] = field(
        default_factory=dict
    )  # 技能冷却计数器，键为技能 id，值为剩余冷却回合数
    res: Dict[str, int] = field(default_factory=lambda: {"energy": 0})
    alive: bool = True
    skills: List[Skill] = field(default_factory=list)


# ========= 引擎与工具 =========


class SkillEngine:
    def __init__(self, A: Entity, B: Entity, log: List[str]):
        self.A, self.B, self.log = A, B, log

    def foe_of(self, ent: Entity) -> Entity:
        return self.B if ent is self.A else self.A

    def emit(self, event: str, **kwargs):
        """分发事件给双方的技能 & buff hooks"""
        ctx = {"engine": self, **kwargs}
        for ent in (self.A, self.B):
            # 技能 hooks
            for sk in ent.skills:
                hook = sk.hooks.get(event)
                if hook:
                    hook(ent, ctx)
            # Buff hooks
            for bf in list(ent.buffs):
                hook = bf.hooks.get(event)
                if hook:
                    hook(ent, ctx)


# ---- Buff 工具 ----


def add_buff(target: Entity, buff: Buff, log: List[str]):
    for b in target.buffs:
        if b.id == buff.id:
            if b.stacks < b.max_stacks:
                b.stacks += 1
            b.duration = max(b.duration, buff.duration)
            log.append(f"{target.name} 的 {b.name} 叠加至 {b.stacks}")
            return
    target.buffs.append(buff)
    log.append(f"{target.name} 获得状态：{buff.name}")


def tick_buffs_end_of_turn(ent: Entity, log: List[str]):
    remain: List[Buff] = []
    for b in ent.buffs:
        if b.duration == -1:
            remain.append(b)
            continue
        b.duration -= 1
        if b.duration <= 0:
            log.append(f"{ent.name} 的 {b.name} 结束")
        else:
            remain.append(b)
    ent.buffs = remain


def final_stat(ent: Entity) -> Dict[str, float]:
    ATK = ent.base["ATK"]
    DEF = ent.base["DEF"]
    HPmax = ent.base["HP"]
    SPD = ent.base["SPD"]
    CRIT = ent.base["CRIT"]
    add = {"ATK": 0.0, "DEF": 0.0, "HP": 0.0, "SPD": 0.0, "CRIT": 0.0}
    mul = {"ATK": 0.0, "DEF": 0.0, "HP": 0.0, "SPD": 0.0, "CRIT": 0.0}
    for b in ent.buffs:
        eff = b.effect
        add["ATK"] += eff.get("ATK+", 0)
        add["DEF"] += eff.get("DEF+", 0)
        add["HP"] += eff.get("HP+", 0)
        add["SPD"] += eff.get("SPD+", 0)
        add["CRIT"] += eff.get("CRIT+", 0)
        mul["ATK"] += eff.get("ATK%", 0)
        mul["DEF"] += eff.get("DEF%", 0)
        mul["HP"] += eff.get("HP%", 0)
        mul["SPD"] += eff.get("SPD%", 0)
        mul["CRIT"] += eff.get("CRIT%", 0)
    ATK = (ATK * (1 + mul["ATK"])) + add["ATK"]
    DEF = (DEF * (1 + mul["DEF"])) + add["DEF"]
    SPD = (SPD * (1 + mul["SPD"])) + add["SPD"]
    HPm = (HPmax * (1 + mul["HP"])) + add["HP"]
    CRI = min(100.0, (CRIT * (1 + mul["CRIT"])) + add["CRIT"])
    return {"ATK": ATK, "DEF": DEF, "SPD": SPD, "HPmax": HPm, "CRIT": CRI}


def roll_damage(
    attacker: Entity, defender: Entity, mult: float = 1.0
) -> tuple[int, bool]:
    su = final_stat(attacker)
    st = final_stat(defender)
    base = max(1.0, su["ATK"] - 0.5 * st["DEF"])
    dmg = int(max(1, base * random.uniform(0.95, 1.05) * mult))
    crit = random.randint(1, 100) <= int(su["CRIT"])
    if crit:
        dmg = int(dmg * 1.5)
    return dmg, crit


# ========= 示例技能实现 =========


# 主动：重击（倍率伤害 + 冷却2）
def use_power_strike(user: Entity, target: Entity, engine: SkillEngine):
    dmg, crit = roll_damage(user, target, mult=1.6)
    target.hp -= dmg
    engine.log.append(
        f"{user.name}【重击】→ {target.name} {dmg}{'（暴击）' if crit else ''}｜剩 {max(0,int(target.hp))}"
    )
    engine.emit("on_deal_damage", actor=user, target=target, damage=dmg, crit=crit)
    engine.emit("on_receive_damage", target=target, actor=user, damage=dmg, crit=crit)


# 主动：迅捷（自我加速2回合，CD3）
def use_quick_aura(user: Entity, target: Entity, engine: SkillEngine):
    haste = Buff(
        id="haste", name="迅捷", effect={"SPD%": 0.25}, duration=2, max_stacks=1
    )
    add_buff(user, haste, engine.log)


# 被动：嗜血（当敌方HP<50%时，本回合 ATK%+20%）
def hook_berserk(ent: Entity, ctx: Dict):
    engine: SkillEngine = ctx["engine"]
    foe = engine.foe_of(ent)
    stats_foe = final_stat(foe)
    if foe.hp <= stats_foe["HPmax"] * 0.5:
        add_buff(
            ent,
            Buff(
                id="berserk",
                name="嗜血",
                effect={"ATK%": 0.2},
                duration=1,
                max_stacks=1,
            ),
            engine.log,
        )


berserk_passive = Skill(
    id="passive_berserk",
    name="嗜血本能",
    type="passive",
    hooks={"on_turn_start": hook_berserk},
)


# 被动：荆棘（受击反伤 15%）
def hook_thorns(ent: Entity, ctx: Dict):
    attacker: Entity = ctx.get("actor")
    dmg: int = ctx.get("damage", 0)
    if not attacker or dmg <= 0:
        return
    refl = max(1, int(dmg * 0.15))
    attacker.hp -= refl
    ctx["engine"].log.append(f"{ent.name}【荆棘】反伤 {attacker.name} {refl}")


thorns_passive = Skill(
    id="passive_thorns",
    name="荆棘甲",
    type="passive",
    hooks={"on_receive_damage": hook_thorns},
)


# 被动：吸血（造成伤害后 恢复等比生命）
def hook_lifesteal(ent: Entity, ctx: Dict):
    damage: int = ctx.get("damage", 0)
    if damage <= 0:
        return
    heal = max(1, int(damage * 0.2))
    ent.hp = int(min(final_stat(ent)["HPmax"], ent.hp + heal))
    ctx["engine"].log.append(f"{ent.name}【吸血】回复 {heal} 点生命")


lifesteal_passive = Skill(
    id="passive_lifesteal",
    name="吸血",
    type="passive",
    hooks={"on_deal_damage": hook_lifesteal},
)

# ========= 技能库 & 装备策略 =========

SKILL_LIBRARY = {
    "POWER_STRIKE": lambda: Skill(
        id="active_power", name="重击", type="active", cd=2, use=use_power_strike
    ),
    "QUICK_AURA": lambda: Skill(
        id="active_quick", name="迅捷", type="active", cd=3, use=use_quick_aura
    ),
    "BERSERK": lambda: berserk_passive,
    "THORNS": lambda: thorns_passive,
    "LIFESTEAL": lambda: lifesteal_passive,
}


def equip_skills_for_player(player: Dict, ent: Entity):
    """按照武器评分发技能（示例策略，可自定义）"""
    slots = player["weapon"]["slots"]
    score = int(slots[0] * 1 + slots[1] * 2 + slots[2] * 3)
    ent.skills = []
    ent.cds = {}
    # 被动：所有人初始给嗜血
    ent.skills.append(SKILL_LIBRARY["BERSERK"]())
    # 评分阈值解锁
    if score >= 12:
        ent.skills.append(SKILL_LIBRARY["POWER_STRIKE"]())
        ent.cds["active_power"] = 0
    if score >= 18:
        ent.skills.append(SKILL_LIBRARY["QUICK_AURA"]())
        ent.cds["active_quick"] = 0
    if score >= 20:
        ent.skills.append(SKILL_LIBRARY["THORNS"]())
    if score >= 22:
        ent.skills.append(SKILL_LIBRARY["LIFESTEAL"]())
