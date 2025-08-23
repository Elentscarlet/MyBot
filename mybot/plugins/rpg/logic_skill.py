# mybot/plugins/rpg/logic_skill.py
# -*- coding: utf-8 -*-
"""
逻辑说明（表驱动版，仅保留“配发技能”能力）：
- 只从 data/equip.yaml 解析“武器评分 -> 技能ID列表”，然后由引擎基于 data/skills.yaml 构造运行期技能对象
- 不再使用任何旧的写死技能库；若没有匹配到任何技能，会兜底发放 basic_attack
- 冷却(cd)与资源(cost)的校验/扣除，建议由上层 BattleManager 或 handlers 处理
"""

from __future__ import annotations
from typing import List, Any
from .battle.entity import Entity  # type: ignore
from .engine.skill_engine import SkillEngine  # type: ignore


__all__ = [
    "equip_skills_for_player",
    "score_from_weapon",
]


def score_from_weapon(player: Any) -> int:
    """
    根据你项目中“武器槽 -> 分值”的规则计算 score。
    - 兼容对象属性与 dict 两种情况：
        对象：player.weapon.slots -> [s1, s2, s3]
        字典：player["weapon"]["slots"]
    - 算法：score = s1*1 + s2*2 + s3*3（与既有实现保持一致）
    """
    # 取出 slots
    if hasattr(player, "weapon") and hasattr(player.weapon, "slots"):
        slots = list(getattr(player.weapon, "slots"))
    else:
        slots = list(player.get("weapon", {}).get("slots", []))  # type: ignore

    # 容错：长度不足时补零
    while len(slots) < 3:
        slots.append(0)

    s1, s2, s3 = int(slots[0]), int(slots[1]), int(slots[2])
    return int(s1 * 1 + s2 * 2 + s3 * 3)


def equip_skills_for_player(player: Any, ent: Entity) -> None:
    """
    为玩家实体配发技能（完全表驱动）：
    1) 用 score_from_weapon(player) 计算 score
    2) 通过 SkillEngine.match_equip_rules(score) 获取技能 ID 列表
    3) 用 SkillEngine.build_skill_from_id(...) 构造运行期技能，填入 ent.skills
    4) 若最终没有任何技能，则兜底发 basic_attack
    5) 初始化 ent.cds 中对应技能的冷却计数为 0（便于外层管理）
    """
    # 引擎引用：约定实体在入队/入场时由上层注入 .engine
    if not hasattr(ent, "engine") or ent.engine is None:
        raise RuntimeError("Entity.engine 未注入 SkillEngine，无法配发技能。")

    eng: SkillEngine = ent.engine  # type: ignore

    # 1) 计算分值
    score = score_from_weapon(player)

    # 2) 按 equip.yaml 规则产出技能ID列表
    skill_ids: List[str] = eng.match_equip_rules(score)

    # 3) 根据 ID 构造运行期技能
    ent.skills = getattr(ent, "skills", [])
    for sid in skill_ids:
        s = eng.build_skill_from_id(sid)
        if s:
            ent.skills.append(s)

    # 4) 兜底：最少拥有 basic_attack
    if not ent.skills:
        s = eng.build_skill_from_id("basic_attack")
        if s:
            ent.skills.append(s)

    # 5) 初始化冷却表（cd 表置0，等待外层在释放后设置真实 cd）
    ent.cds = getattr(ent, "cds", {})
    for s in ent.skills:
        if getattr(s, "cd", 0) > 0 and s.id not in ent.cds:
            ent.cds[s.id] = 0
