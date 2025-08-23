# -*- coding: utf-8 -*-
import os, json, time, threading
from typing import Dict

DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)
PLAYERS_JSON = os.path.join(DATA_DIR, "players.json")
BOSS_JSON = os.path.join(DATA_DIR, "boss.json")
_json_lock = threading.Lock()


def _load_json(path: str, default):
    with _json_lock:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default


def _save_json(path: str, obj):
    with _json_lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def today_tag() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def load_players() -> Dict[str, Dict]:
    return _load_json(PLAYERS_JSON, {})


def save_players(players: Dict[str, Dict]):
    _save_json(PLAYERS_JSON, players)


def load_boss_map() -> Dict[str, Dict]:
    return _load_json(BOSS_JSON, {})


def save_boss_map(boss_map: Dict[str, Dict]):
    _save_json(BOSS_JSON, boss_map)
