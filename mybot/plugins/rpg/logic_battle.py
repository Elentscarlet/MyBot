# mybot/plugins/rpg/logic_battle.py
# -*- coding: utf-8 -*-
"""
战斗逻辑（表驱动版入口）：
- 保留 derive_internal_stats（兼容老面板读取）
- 新增 simulate_duel_with_skills：事件驱动技能战斗（不再走旧的即时数值结算）
"""
from __future__ import annotations

import pathlib
from typing import Dict, Tuple, List

import yaml

from mybot.plugins.rpg.battle.adapters import player_to_entity, monster_to_entity
from mybot.plugins.rpg.engine.battle_system import BattleSystem
from mybot.plugins.rpg.engine.skill_engine import SkillEngine
from mybot.plugins.rpg.logic_skill import equip_skills_for_player
from mybot.plugins.rpg.util.config_loader import ConfigLoader
from mybot.plugins.rpg.util.skill_factory import SkillFactory


# === 兼容：老面板推导（如有外部依赖就保留；这里给一个最简实现） ===
def derive_internal_stats(player) -> Dict[str, int]:
    """将玩家点数/装备映射为面板数值（供外部 UI/日志读取）。"""
    atk = getattr(player.points, "str", 0) + getattr(player.weapon, "atk", 0)
    dfn = getattr(player.points, "def", 0) + getattr(player.weapon, "def", 0)
    agi = getattr(player.points, "agi", 0) + getattr(player.weapon, "agi", 0)
    itl = getattr(player.points, "int", 0) + getattr(player.weapon, "int", 0)
    hp = (getattr(player.points, "hp", 0) + getattr(player.weapon, "hp", 0)) * 10
    crt = max(0.0, min(1.0, getattr(player.points, "crit", 0) / 100.0))
    return {"ATK": atk, "DEF": dfn, "AGI": agi, "INT": itl, "MAX_HP": hp, "CRIT": crt}


# === 工具：加载怪物定义 ===
def _load_monster_def(monster_id: str) -> Dict:
    path = pathlib.Path(__file__).resolve().parent / "battle" / "monsters.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    print(data)
    for m in data:
        if str(m.get("id")) == str(monster_id):
            return m
    raise KeyError(f"monster id not found: {monster_id}")


# === 核心：跑一场 1v1（或 组队可拓展） ===
def simulate_duel_with_skills(
        player,
        monster_id: str,
        boss_hp: int | None = None,
        max_turns: int = 10,
        seed: int | None = None,
) -> Tuple[str, List[str],int]:
    """
    事件驱动技能战斗（最小复现）：
    - 100% 走 YAML（skills/buffs/equip）
    - 主动技释放前的 cd 由此函数管理；资源(cost)留给上层按项目规则处理
    返回值：(result, logs)
    """
    config_loader = ConfigLoader()
    battle_system = BattleSystem()
    skill_factory = SkillFactory(config_loader, battle_system.event_bus)

    # 1) 构建实体
    eng = SkillEngine(seed=seed)
    p_ent = player_to_entity(player)
    m_def = _load_monster_def(monster_id)
    m_ent = monster_to_entity(m_def, hp=boss_hp)

    # 互相注入 engine（让技能/ops 能访问 rng / buff_defs 等）
    p_ent.engine = eng
    m_ent.engine = eng

    # 2) 配发技能
    equip_skills_for_player(player, p_ent,skill_factory)

    # 怪物最少也能普攻；若你有更复杂AI与技能表，在此接入
    m_basic = eng.build_skill_from_id("basic_attack")
    if m_basic:
        skill = skill_factory.create_skill("basic_attack", m_ent)
        m_ent.skills.append(skill)

    # 添加到战斗系统
    battle_system.add_unit(p_ent)
    battle_system.add_unit(m_ent)
    battle_system.report_mode = player.config.battle_report_model

    # 开始战斗
    battle_system.start_battle(p_ent, m_ent, max_turns)
    return battle_system.winner, battle_system.battle_log , m_ent.HP


def simulate_pvp_with_skills(
        player_a, player_b, max_turns: int = 10, seed: int | None = None
) -> tuple[str, str]:
    config_loader = ConfigLoader()
    battle_system = BattleSystem()
    skill_factory = SkillFactory(config_loader, battle_system.event_bus)

    ent_a = player_to_entity(player_a)
    ent_b = player_to_entity(player_b)
    eng = SkillEngine(seed=seed)
    ent_a.engine = eng
    ent_b.engine = eng

    equip_skills_for_player(player_a, ent_a,skill_factory)
    equip_skills_for_player(player_b, ent_b,skill_factory)

    # 添加到战斗系统
    battle_system.add_unit(ent_a)
    battle_system.add_unit(ent_b)
    battle_system.report_mode = player_a.config.battle_report_model

    # 开始战斗
    battle_system.start_battle(ent_a,ent_b,max_turns)
    return battle_system.winner,battle_system.battle_log


# ===== 冷却与择技（最小实现） =====
def _pick_castable_skill_id(ent) -> str | None:
    """优先返回第一个主动技ID；若ent没有技能则返回None。"""
    for s in getattr(ent, "skills", []):
        if getattr(s, "type", "active") == "active":
            return s.id
    return None


def _cd_ready(ent, sid: str) -> bool:
    cds = getattr(ent, "cds", {})
    return cds.get(sid, 0) <= 0


def _set_cd_after_cast(ent, sid: str, eng: SkillEngine):
    """施放后设置冷却：以表中该技能的 cd 为准；若无定义则为0。"""
    sdef = eng.skill_defs.get(sid) or {}
    cd = int(sdef.get("cd", 0))
    ent.cds[sid] = cd
    # 全局推进其它冷却 - 1（可选，如果你的项目是回合末统一-1，此处可以移到回合末统一处理）
    for k in list(ent.cds.keys()):
        if k != sid and ent.cds[k] > 0:
            ent.cds[k] -= 1



