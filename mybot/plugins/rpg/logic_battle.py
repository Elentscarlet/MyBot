# mybot/plugins/rpg/logic_battle.py
# -*- coding: utf-8 -*-
"""
战斗逻辑（表驱动版入口）：
- 保留 derive_internal_stats（兼容老面板读取）
- 新增 simulate_duel_with_skills：事件驱动技能战斗（不再走旧的即时数值结算）
"""
from __future__ import annotations
from typing import Dict, Tuple, List
import pathlib
import yaml
import random

from .engine.skill_engine import SkillEngine
from .battle.adapters import player_to_entity, monster_to_entity
from .logic_skill import equip_skills_for_player


# === 兼容：老面板推导（如有外部依赖就保留；这里给一个最简实现） ===
def derive_internal_stats(player) -> Dict[str, int]:
    """将玩家点数/装备映射为面板数值（供外部 UI/日志读取）。"""
    atk = player.points.get("str", 0) + getattr(player.weapon, "atk", 0)
    dfn = player.points.get("def", 0) + getattr(player.weapon, "def", 0)
    agi = player.points.get("agi", 0) + getattr(player.weapon, "agi", 0)
    itl = player.points.get("int", 0) + getattr(player.weapon, "int", 0)
    hp = (player.points.get("hp", 0) + getattr(player.weapon, "hp", 0)) * 10
    crt = max(0.0, min(1.0, player.points.get("crit", 0) / 100.0))
    return {"ATK": atk, "DEF": dfn, "AGI": agi, "INT": itl, "MAX_HP": hp, "CRIT": crt}


# === 工具：加载怪物定义 ===
def _load_monster_def(monster_id: str) -> Dict:
    path = pathlib.Path(__file__).resolve().parent / "battle" / "monsters.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    for m in data:
        if str(m.get("id")) == str(monster_id):
            return m
    raise KeyError(f"monster id not found: {monster_id}")


# === 核心：跑一场 1v1（或 组队可拓展） ===
def simulate_duel_with_skills(
    player, monster_id: str, max_turns: int = 6, seed: int | None = None
) -> Tuple[str, List[str]]:
    """
    事件驱动技能战斗（最小复现）：
    - 100% 走 YAML（skills/buffs/equip）
    - 主动技释放前的 cd 由此函数管理；资源(cost)留给上层按项目规则处理
    返回值：(result, logs)
    """
    rng = random.Random(seed)

    # 1) 构建实体
    eng = SkillEngine(seed=seed)
    p_ent = player_to_entity(player)
    m_def = _load_monster_def(monster_id)
    m_ent = monster_to_entity(m_def)

    # 注入阵营
    p_ent.set_allies([p_ent])
    p_ent.set_enemies([m_ent])
    m_ent.set_allies([m_ent])
    m_ent.set_enemies([p_ent])

    # 互相注入 engine（让技能/ops 能访问 rng / buff_defs 等）
    p_ent.engine = eng
    m_ent.engine = eng

    # 2) 配发技能
    equip_skills_for_player(player, p_ent)
    # 怪物最少也能普攻；若你有更复杂AI与技能表，在此接入
    m_basic = eng.build_skill_from_id("basic_attack")
    if m_basic:
        m_ent.skills = getattr(m_ent, "skills", [])
        m_ent.skills.append(m_basic)

    # 初始化冷却表
    for e in (p_ent, m_ent):
        e.cds = getattr(e, "cds", {})
        for s in getattr(e, "skills", []):
            if getattr(s, "cd", 0) > 0 and s.id not in e.cds:
                e.cds[s.id] = 0

    logs: List[str] = []
    logs.append(f"【对战开始】{p_ent.name} vs {m_ent.name}")

    # 3) 开始（可选）战斗开始事件
    eng.emit("on_battle_start", p_ent)
    eng.emit("on_battle_start", m_ent)

    # 4) 回合循环
    actors = [p_ent, m_ent]
    for turn in range(1, max_turns + 1):
        logs.append(f"—— 第 {turn} 回合 ——")
        for actor in actors:
            if not actor.is_alive():
                continue
            target_side = m_ent if actor is p_ent else p_ent
            if not target_side.is_alive():
                break

            # 回合开始
            eng.emit("on_turn_start", actor)
            eng.tick_buffs(actor)

            # 选择一个可用主动技（否则普攻）
            sid = _pick_castable_skill_id(actor)
            if sid is None:
                sid = "basic_attack"  # 兜底

            # 冷却校验
            if _cd_ready(actor, sid):
                ok = eng.cast(actor, sid)
                if ok:
                    _set_cd_after_cast(actor, sid, eng)
                logs.extend(eng.log)
                eng.log.clear()
            else:
                # 冷却未就绪，使用普攻（若普攻本身在冷却则跳过）
                if sid != "basic_attack" and _cd_ready(actor, "basic_attack"):
                    eng.cast(actor, "basic_attack")
                    _set_cd_after_cast(actor, "basic_attack", eng)
                    logs.extend(eng.log)
                    eng.log.clear()
                else:
                    logs.append(f"{actor.name} 暂无法行动（冷却中）")

            # 回合结束
            eng.emit("on_turn_end", actor)
            eng.tick_buffs(actor)

            # 胜负判断
            if not p_ent.is_alive() and not m_ent.is_alive():
                logs.append("双方同时倒地，平局")
                return "draw", logs
            if not p_ent.is_alive():
                logs.append(f"{p_ent.name} 倒地，{m_ent.name} 获胜")
                return "lose", logs
            if not m_ent.is_alive():
                logs.append(f"{m_ent.name} 倒地，{p_ent.name} 获胜")
                return "win", logs

    logs.append("达到最大回合数，判定平局")
    return "draw", logs


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
