# -*- coding: utf-8 -*-
from typing import Dict, List
from .storage import today_tag, load_players, save_players, load_boss_map, save_boss_map


def default_player(uid: str, gid: str, name: str) -> Dict:
    return {
        "uid": uid,
        "gid": gid,
        "name": name,
        "level": 1,
        "unspent": 0,
        "points": {"str": 0, "def": 0, "hp": 0, "agi": 0, "crit": 0},
        "weapon": {"name": "无名之刃", "slots": [1, 1, 1]},  # C=1,B=2,A=3,S=4
        "dust": 0,
        "diamond": 0,
        "tear": 0,
        "ticket": 0,
        "counters": {
            "daily_date": today_tag(),
            "free_explore_used": 0,
            "boss_hits": 0,
            "signed": False,
        },
    }


def default_boss(gid: str) -> Dict:
    return {
        "gid": gid,
        "boss_date": today_tag(),
        "name": "远古巨像",
        "hp": 3000,
        "hp_max": 3000,
        "atk": 50,
        "def": 15,
        "spd": 10,
        "crit": 10,
        "board": {},
        "killed": False,
    }


def get_player(uid: str, gid: str, name: str) -> Dict:
    players = load_players()
    key = f"{gid}:{uid}"
    p = players.get(key)
    if not p:
        p = default_player(uid, gid, name)
        players[key] = p
        save_players(players)
    else:
        if p["counters"]["daily_date"] != today_tag():
            p["counters"] = {
                "daily_date": today_tag(),
                "free_explore_used": 0,
                "boss_hits": 0,
                "signed": False,
            }
            players[key] = p
            save_players(players)
    return p


def put_player(p: Dict):
    players = load_players()
    key = f'{p["gid"]}:{p["uid"]}'
    players[key] = p
    save_players(players)


def get_boss(gid: str) -> Dict:
    bm = load_boss_map()
    b = bm.get(gid)
    if (not b) or (b["boss_date"] != today_tag()):
        b = default_boss(gid)
        bm[gid] = b
        save_boss_map(bm)
    return b


def put_boss(b: Dict):
    bm = load_boss_map()
    bm[b["gid"]] = b
    save_boss_map(bm)


# 评分/段位/精炼
def score_of_slots(slots: List[int]) -> int:
    return int(slots[0] * 1 + slots[1] * 2 + slots[2] * 3)


def slots_to_rank(slots: List[int]) -> str:
    return "".join({1: "C", 2: "B", 3: "A", 4: "S"}[x] for x in slots)


def refine_cost(next_val: int) -> int:
    return {2: 100, 3: 300, 4: 900}.get(next_val, 999999)
