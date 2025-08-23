# mybot/plugins/rpg/logic_battle.py
# -*- coding: utf-8 -*-
"""
战斗逻辑：
- 保留 derive_internal_stats（兼容老面板）
- 新增 simulate_duel_with_skills：事件驱动技能战斗
"""
import random
from typing import Dict, Tuple
from .models import Player

# 如果你的项目里还保留旧版 simulate_duel，可与新版并存
# from .logic_battle import simulate_duel  # 老函数（可删除）


# --- 面板/内在数值推导（保持原样，供 handlers 读取） ---
def derive_internal_stats(p: Player) -> Dict[str, float]:
    Lv = p.level
    pts = p.points
    slots = p.weapon.slots
    score = int(slots[0] * 1 + slots[1] * 2 + slots[2] * 3)
    atk = 6 + 2 * score + Lv + 2 * pts.str
    dfn = 4 + Lv + 1.5 * pts.def_
    hp = 80 + 10 * Lv + 12 * pts.hp
    spd = 8 + (Lv // 2) + 0.6 * pts.agi
    cri = min(30, 10 + 0.8 * pts.crit)
    return {"ATK": atk, "DEF": dfn, "HP": hp, "SPD": spd, "CRIT": cri}


# --- 新：技能引擎版战斗 ---
from .logic_skill import (
    Entity,
    SkillEngine,
    final_stat,
    tick_buffs_end_of_turn,
    use_power_strike,
    use_quick_aura,  # 仅示例；无需直接使用
)


def _choose_action(actor: Entity, target: Entity):
    """简易AI：优先可用主动技能（按名称约定），否则普攻"""
    # 按我们在 equip_skills_for_player 中的ID命名，检查 CD 字典
    if actor.cds.get("active_power", 0) <= 0:

        def act(eng: SkillEngine):
            from .logic_skill import use_power_strike

            use_power_strike(actor, target, eng)
            actor.cds["active_power"] = 2

        return "重击", act

    if actor.cds.get("active_quick", 0) <= 0:

        def act(eng: SkillEngine):
            from .logic_skill import use_quick_aura

            use_quick_aura(actor, actor, eng)
            actor.cds["active_quick"] = 3

        return "迅捷", act

    # 普攻
    def act_basic(eng: SkillEngine):
        su = final_stat(actor)
        st = final_stat(target)
        base = max(1.0, su["ATK"] - 0.5 * st["DEF"])
        dmg = int(max(1, base * random.uniform(0.95, 1.05)))
        crit = random.randint(1, 100) <= int(su["CRIT"])
        if crit:
            dmg = int(dmg * 1.5)
        target.hp -= dmg
        eng.log.append(
            f"{actor.name} 普攻 → {target.name} {dmg}{'（暴击）' if crit else ''}｜剩 {max(0,int(target.hp))}"
        )
        eng.emit("on_deal_damage", actor=actor, target=target, damage=dmg, crit=crit)
        eng.emit("on_receive_damage", target=target, actor=actor, damage=dmg, crit=crit)

    return "普攻", act_basic


def simulate_duel_with_skills(
    a_name: str,
    a_stat: Dict[str, float],
    b_name: str,
    b_stat: Dict[str, float],
    equip_A=None,
    equip_B=None,
    max_rounds: int = 30,
) -> Tuple[str, str]:
    """
    equip_A/equip_B: 可传入函数(player, entity)，用于“装备技能”，
                     如果不传，则按外部已配置的 cds/skills 执行。
    """
    A = Entity(name=a_name, base=a_stat, hp=int(a_stat["HP"]))
    B = Entity(name=b_name, base=b_stat, hp=int(b_stat["HP"]))
    log = []
    eng = SkillEngine(A, B, log)

    # 如果外部传了装备函数（比如基于玩家/武器评分），这里让他注入技能
    if equip_A:
        equip_A(A)
    if equip_B:
        equip_B(B)

    # 开战事件（处理被动的开场效果/光环）
    eng.emit("on_battle_start")

    # 先手
    turn = A if final_stat(A)["SPD"] >= final_stat(B)["SPD"] else B
    other = B if turn is A else A
    log.append(f"【对战开始】先手：{turn.name}")

    rounds = 0
    while A.alive and B.alive and rounds < max_rounds:
        rounds += 1
        for actor, target in ((turn, other), (other, turn)):
            if not (A.alive and B.alive):
                break

            # 回合开始
            eng.emit("on_turn_start", actor=actor)

            # 选择行动
            sid, action = _choose_action(actor, target)
            eng.emit("on_before_skill", actor=actor, target=target, skill=sid)

            # 执行
            action(eng)

            # 判死亡
            if target.hp <= 0:
                target.hp = 0
                target.alive = False
                eng.emit("on_death", entity=target)
                log.append(f"【{target.name} 倒下】")

            # 回合结束：CD-1、Buff tick
            for k in list(actor.cds.keys()):
                actor.cds[k] = max(0, actor.cds[k] - 1)
            tick_buffs_end_of_turn(actor, log)
        # 互换先手
        turn, other = other, turn

    winner = (
        A.name
        if B.hp <= 0
        else (B.name if A.hp <= 0 else (A.name if A.hp >= B.hp else B.name))
    )
    eng.emit("on_battle_end", winner=winner)
    log.append(f"【结果】胜者：{winner}（{rounds}回合）")
    return "\n".join(log[:120]), winner
