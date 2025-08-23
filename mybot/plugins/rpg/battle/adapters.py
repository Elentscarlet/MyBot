# mybot/plugins/rpg/battle/adapters.py
from typing import Dict
from .entity import Entity


def player_to_entity(player) -> Entity:
    """把账号养成数据映射为一个战斗实体；不修改/污染 player 本体。"""
    # 例：简化映射；你可按项目规则换算
    base = {
        "ATK": player.points.get("str", 0) + getattr(player.weapon, "atk", 0),
        "DEF": player.points.get("def", 0) + getattr(player.weapon, "def", 0),
        "AGI": player.points.get("agi", 0) + getattr(player.weapon, "agi", 0),
        "INT": player.points.get("int", 0) + getattr(player.weapon, "int", 0),
        "MAX_HP": (player.points.get("hp", 0) + getattr(player.weapon, "hp", 0)) * 10,
        "CRIT": max(0.0, min(1.0, player.points.get("crit", 0) / 100.0)),
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
