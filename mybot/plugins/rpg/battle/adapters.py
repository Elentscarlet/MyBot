# mybot/plugins/rpg/battle/adapters.py
from typing import Dict
from .entity import Entity

BASE_STATS = {
    "ATK": 1,
    "DEF": 1,
    "AGI": 1,
    "HP": 2,  # 基础HP点数
    "CRIT": 0.05,  # 基础暴击率
}

# 武器评分对属性的百分比加成系数（可根据实际体验调整）
WEAPON_SCORE_COEF = {
    "ATK": 0.05,  # 每分score加5%攻击
    "DEF": 0.04,  # 每分score加4%防御
    "AGI": 0.04,  # 每分score加4%敏捷
    "HP": 0.04,  # 每分score加4%HP
    "CRIT": 0.01,  # 每分score加1%暴击率
}


def player_to_entity(player) -> Entity:
    """把账号养成数据映射为一个战斗实体；不修改/污染 player 本体。"""
    weapon_score = getattr(player.weapon, "score", 0)

    # 先计算基础属性（不含武器加成）
    base_atk = (BASE_STATS["ATK"]
                + getattr(player.points, "str", 0)
                + getattr(player.extra_points, "str", 0))
    base_def = (BASE_STATS["DEF"]
                + getattr(player.points, "def_", 0)
                + getattr(player.extra_points, "def_", 0))
    base_agi = (BASE_STATS["AGI"]
                + getattr(player.points, "agi", 0)
                + getattr(player.extra_points, "agi", 0))
    base_hp = (BASE_STATS["HP"]
               + getattr(player.points, "hp", 0)
               + getattr(player.extra_points, "hp", 0))

    # 应用武器百分比加成
    base = {
        "ATK": base_atk * (1 + weapon_score * WEAPON_SCORE_COEF["ATK"]),
        "DEF": base_def * (1 + weapon_score * WEAPON_SCORE_COEF["DEF"]),
        "AGI": base_agi * (1 + weapon_score * WEAPON_SCORE_COEF["AGI"]),
        "MAX_HP": base_hp * 10 * (1 + weapon_score * WEAPON_SCORE_COEF["HP"]),
        "CRIT": min(
            1.0,
            max(
                0.0,
                BASE_STATS["CRIT"]
                # 一点暴击属性 2%暴击
                + (getattr(player.points, "crit", 0) + getattr(player.extra_points, "crit", 0)) / 50.0
                + weapon_score * WEAPON_SCORE_COEF["CRIT"],
            ),
        ),
    }
    return Entity(name=player.name, base_stats=base, tag="player")


def monster_to_entity(mdef: Dict, hp: int = None) -> Entity:
    base = {
        "ATK": int(mdef["ATK"]),
        "DEF": int(mdef["DEF"]),
        "AGI": int(mdef.get("AGI", 0)),
        "INT": int(mdef.get("INT", 0)),
        "MAX_HP": int(mdef["MAX_HP"]),
        "CRIT": float(mdef.get("CRIT", 0.0)),
    }
    ent = Entity(name=mdef["name"], base_stats=base, tag=mdef.get("tag", "monster"))
    if hp is not None:
        ent.HP = hp
    return ent
