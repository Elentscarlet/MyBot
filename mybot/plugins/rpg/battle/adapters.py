# mybot/plugins/rpg/battle/adapters.py
from typing import Dict
from .entity import Entity

BASE_STATS = {
    "ATK": 5,
    "DEF": 3,
    "AGI": 3,
    "INT": 3,
    "HP": 10,  # 基础HP点数
    "CRIT": 0.05,  # 基础暴击率
}


def player_to_entity(player) -> Entity:
    """把账号养成数据映射为一个战斗实体；不修改/污染 player 本体。"""
    base = {
        "ATK": BASE_STATS["ATK"]
        + getattr(player.points, "str", 0)
        + getattr(player.weapon, "atk", 0),
        "DEF": BASE_STATS["DEF"]
        + getattr(player.points, "def", 0)
        + getattr(player.weapon, "def", 0),
        "AGI": BASE_STATS["AGI"]
        + getattr(player.points, "agi", 0)
        + getattr(player.weapon, "agi", 0),
        "INT": BASE_STATS["INT"]
        + getattr(player.points, "int", 0)
        + getattr(player.weapon, "int", 0),
        "MAX_HP": (
            BASE_STATS["HP"]
            + getattr(player.points, "hp", 0)
            + getattr(player.weapon, "hp", 0)
        )
        * 10,
        "CRIT": min(
            1.0,
            max(0.0, BASE_STATS["CRIT"] + getattr(player.points, "crit", 0) / 100.0),
        ),
    }
    return Entity(name=player.name, base_stats=base, tag="player")


def monster_to_entity(mdef: Dict) -> Entity:
    """从 monsters.yaml 中的一条怪物定义构造战斗实体。"""
    base = {
        "ATK": int(mdef["ATK"]),
        "DEF": int(mdef["DEF"]),
        "AGI": int(mdef.get("AGI", 0)),
        "INT": int(mdef.get("INT", 0)),
        "MAX_HP": int(mdef["MAX_HP"]),
        "CRIT": float(mdef.get("CRIT", 0.0)),  # 0~1
    }
    return Entity(name=mdef["name"], base_stats=base, tag=mdef.get("tag", "monster"))
