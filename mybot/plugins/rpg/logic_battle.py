# -*- coding: utf-8 -*-
import random
from typing import Dict, Tuple, List


def derive_internal_stats(p: Dict) -> Dict[str, float]:
    Lv = p["level"]
    pts = p["points"]
    slots = p["weapon"]["slots"]
    score = int(slots[0] * 1 + slots[1] * 2 + slots[2] * 3)
    atk = 6 + 2 * score + Lv + 2 * pts["str"]
    dfn = 4 + Lv + 1.5 * pts["def"]
    hp = 80 + 10 * Lv + 12 * pts["hp"]
    spd = 8 + (Lv // 2) + 0.6 * pts["agi"]
    crit = min(30, 10 + 0.8 * pts["crit"])
    return {"ATK": atk, "DEF": dfn, "HP": hp, "SPD": spd, "CRIT": crit}


def damage_calc(
    atk: float, dfn: float, mult: float = 1.0, bonus_crit: int = 0
) -> Tuple[int, bool]:
    base = max(1.0, atk - 0.5 * dfn)
    roll = random.uniform(0.95, 1.05)
    dmg = max(1, int(base * roll * mult))
    if random.randint(1, 100) <= min(100, 10 + bonus_crit):
        return int(dmg * 1.5), True
    return dmg, False


def simulate_duel(
    a_name: str,
    a_stat: Dict[str, float],
    b_name: str,
    b_stat: Dict[str, float],
    max_rounds: int = 30,
) -> Tuple[str, str]:
    a_hp = int(a_stat["HP"])
    b_hp = int(b_stat["HP"])
    a_atk = a_stat["ATK"]
    b_atk = b_stat["ATK"]
    a_def = a_stat["DEF"]
    b_def = b_stat["DEF"]
    a_spd = a_stat["SPD"]
    b_spd = b_stat["SPD"]
    turn = a_name if a_spd >= b_spd else b_name

    log = [f"【对战开始】先手：{turn}"]
    rounds = 0
    while a_hp > 0 and b_hp > 0 and rounds < max_rounds:
        rounds += 1
        for actor in (turn, (b_name if turn == a_name else a_name)):
            if a_hp <= 0 or b_hp <= 0:
                break
            if actor == a_name:
                dmg, crit = damage_calc(a_atk, b_def, 1.0)
                b_hp -= dmg
                log.append(
                    f"R{rounds}: {a_name} 普攻 → {dmg}{'（暴击）' if crit else ''} | {b_name} 剩 {max(0,b_hp)}"
                )
            else:
                dmg, crit = damage_calc(b_atk, a_def, 1.0)
                a_hp -= dmg
                log.append(
                    f"R{rounds}: {b_name} 普攻 → {dmg}{'（暴击）' if crit else ''} | {a_name} 剩 {max(0,a_hp)}"
                )
        turn = b_name if turn == a_name else a_name

    winner = (
        a_name
        if b_hp <= 0
        else b_name if a_hp <= 0 else (a_name if a_hp >= b_hp else b_name)
    )
    log.append(f"【结果】胜者：{winner}（{rounds}回合）")
    return "\n".join(log[:80]), winner
