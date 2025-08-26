# mybot/plugins/rpg/battle/adapters.py
from typing import Dict
from .entity import Entity

BASE_STATS = {
    "ATK": 5,
    "DEF": 3,
    "AGI": 3,
    "INT": 3,
    "HP": 2,  # 基础HP点数
    "CRIT": 0.05,  # 基础暴击率
}

# 武器评分对属性的加成系数（可根据实际体验调整）
WEAPON_SCORE_COEF = {
    "ATK": 0.7,
    "DEF": 0.4,
    "AGI": 0.3,
    "INT": 0.2,
    "HP": 0.5,  # 每分score加多少点HP
    "CRIT": 0.01,  # 每分score加多少暴击率
}


def player_to_entity(player) -> Entity:
    """把账号养成数据映射为一个战斗实体；不修改/污染 player 本体。"""
    weapon_score = getattr(player.weapon, "score", 0)
    base = {
        "ATK": BASE_STATS["ATK"]
               + getattr(player.points, "str", 0)
               + getattr(player.extra_points, "str", 0)
               + weapon_score * WEAPON_SCORE_COEF["ATK"],
        "DEF": BASE_STATS["DEF"]
               + getattr(player.points, "def_", 0)
               + getattr(player.extra_points, "def_", 0)
               + weapon_score * WEAPON_SCORE_COEF["DEF"],
        "AGI": BASE_STATS["AGI"]
               + getattr(player.points, "agi", 0)
               + getattr(player.extra_points, "agi", 0)
               + weapon_score * WEAPON_SCORE_COEF["AGI"],
        "MAX_HP": (
                          BASE_STATS["HP"]
                          + getattr(player.points, "hp", 0)
                          + getattr(player.extra_points, "hp", 0)
                          + weapon_score * WEAPON_SCORE_COEF["HP"]
                  )
                  * 10,
        "CRIT": min(
            1.0,
            max(
                0.0,
                BASE_STATS["CRIT"]
                + (getattr(player.points, "crit", 0) + getattr(player.extra_points, "crit", 0)) / 100.0
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
