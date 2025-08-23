# mybot/plugins/rpg.py
# -*- coding: utf-8 -*-
"""
RPG Bot（JSON 存档版，中文口令触发）
- 使用关键词触发，例如“签到”“面板”“十连”“精炼1”“对战 @某人”“出刀”
- 数据存储在 data/players.json, data/boss.json
- 提供帮助菜单
"""

import os, json, time, random, threading, re
from typing import Dict, List, Tuple, Optional
from nonebot import on_keyword, on_regex
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

# =============== 数据文件与存取 ===============
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
            except:
                return default


def _save_json(path: str, obj):
    with _json_lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def today_tag() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


# =============== 默认数据 ===============
def _default_player(uid: str, gid: str, name: str) -> Dict:
    return {
        "uid": uid,
        "gid": gid,
        "name": name,
        "level": 1,
        "unspent": 0,
        "points": {"str": 0, "def": 0, "hp": 0, "agi": 0, "crit": 0},
        "weapon": {"name": "无名之刃", "slots": [1, 1, 1]},  # C=1
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


def _default_boss(gid: str) -> Dict:
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


# =============== 存取封装 ===============
def load_players():
    return _load_json(PLAYERS_JSON, {})


def save_players(p):
    _save_json(PLAYERS_JSON, p)


def load_boss_map():
    return _load_json(BOSS_JSON, {})


def save_boss_map(m):
    _save_json(BOSS_JSON, m)


def get_player(uid, gid, name):
    players = load_players()
    key = f"{gid}:{uid}"
    p = players.get(key)
    if not p:
        p = _default_player(uid, gid, name)
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


def put_player(p):
    players = load_players()
    key = f"{p['gid']}:{p['uid']}"
    players[key] = p
    save_players(players)


def get_boss(gid):
    bm = load_boss_map()
    b = bm.get(gid)
    if (not b) or (b["boss_date"] != today_tag()):
        b = _default_boss(gid)
        bm[gid] = b
        save_boss_map(bm)
    return b


def put_boss(b):
    bm = load_boss_map()
    bm[b["gid"]] = b
    save_boss_map(bm)


# =============== 工具函数 ===============
def _event_ids(event: MessageEvent):
    uid = str(event.user_id)
    gid = str(getattr(event, "group_id", 0))
    try:
        name = event.sender.card or event.sender.nickname
    except:
        name = uid
    return uid, gid, name


def _first_at(event: MessageEvent) -> Optional[str]:
    for seg in event.message:
        if seg.type == "at" and "qq" in seg.data:
            return str(seg.data["qq"])
    return None


def _text(event: MessageEvent) -> str:
    return str(event.get_message()).strip()


def score_of_slots(slots: List[int]) -> int:
    return int(slots[0] * 1 + slots[1] * 2 + slots[2] * 3)


def slots_to_rank(slots: List[int]) -> str:
    return "".join({1: "C", 2: "B", 3: "A", 4: "S"}[x] for x in slots)


def refine_cost(nxt: int) -> int:
    return {2: 100, 3: 300, 4: 900}.get(nxt, 999999)


def gacha10_to_dust():
    stars = []
    for _ in range(10):
        r = random.random()
        stars.append(5 if r < 0.03 else 4 if r < 0.23 else 3)
    dust = sum(600 if s == 5 else 120 if s == 4 else 30 for s in stars)
    return dust, {"5★": stars.count(5), "4★": stars.count(4), "3★": stars.count(3)}


# =============== 战斗模拟 ===============
def derive_internal_stats(p):
    Lv = p["level"]
    pts = p["points"]
    score = score_of_slots(p["weapon"]["slots"])
    atk = 6 + 2 * score + Lv + 2 * pts["str"]
    dfn = 4 + Lv + 1.5 * pts["def"]
    hp = 80 + 10 * Lv + 12 * pts["hp"]
    spd = 8 + (Lv // 2) + 0.6 * pts["agi"]
    crit = min(30, 10 + 0.8 * pts["crit"])
    return {"ATK": atk, "DEF": dfn, "HP": hp, "SPD": spd, "CRIT": crit}


def damage_calc(atk, dfn, mult, bonus=0):
    base = max(1, atk - 0.5 * dfn)
    roll = random.uniform(0.95, 1.05)
    dmg = max(1, int(base * roll * mult))
    if random.randint(1, 100) <= min(100, 10 + bonus):
        return int(dmg * 1.5), True
    return dmg, False


def simulate_duel(a_name, a_stat, b_name, b_stat, max_rounds=30):
    a_hp = int(a_stat["HP"])
    b_hp = int(b_stat["HP"])
    a_spd = a_stat["SPD"]
    b_spd = b_stat["SPD"]
    a_atk = a_stat["ATK"]
    b_atk = b_stat["ATK"]
    a_def = a_stat["DEF"]
    b_def = b_stat["DEF"]
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


# =============== 指令匹配器（中文关键词） ===============

# 帮助
help_m = on_keyword({"帮助", "菜单", "指令", "help"})


@help_m.handle()
async def _():
    await help_m.finish(
        "【RPG帮助】\n"
        "起名 <名字>：设置武器名\n"
        "面板：查看角色\n列表：群玩家\n"
        "签到：每日免费十连\n十连/抽卡：花钻石抽卡\n"
        "精炼1/2/3：精炼槽位\n远征/打野：获得资源\n"
        "对战 @对手：群内对战\nBOSS：查看BOSS\n出刀：攻击BOSS"
    )


# 起名
rename_m = on_regex(r"^(起名|改名)\s*(.+)$")


@rename_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = _event_ids(event)
    p = get_player(uid, gid, name)
    r = re.match(r"^(起名|改名)\s*(.+)$", _text(event))
    new = r.group(2).strip()[:20]
    p["weapon"]["name"] = new
    put_player(p)
    await rename_m.finish(f"已改名：{new}")


# 面板
profile_m = on_keyword({"面板", "状态", "信息"})


@profile_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = _event_ids(event)
    p = get_player(uid, gid, name)
    slots = p["weapon"]["slots"]
    await profile_m.finish(
        f"【面板】{p['name']} Lv.{p['level']}\n"
        f"武器：{p['weapon']['name']}（{slots_to_rank(slots)}｜评分{score_of_slots(slots)}）\n"
        f"加点：力{p['points']['str']} 防{p['points']['def']} 血{p['points']['hp']} 敏{p['points']['agi']} 暴{p['points']['crit']}\n"
        f"未分配点：{p['unspent']}\n"
        f"粉尘：{p['dust']} 钻石：{p['diamond']} 探索券：{p['ticket']} 女神之泪：{p['tear']}\n"
        f"今日：远征{p['counters']['free_explore_used']}/2 出刀{p['counters']['boss_hits']}/3 签到：{'已' if p['counters']['signed'] else '未'}"
    )


# 列表
list_m = on_keyword({"列表", "成员", "玩家"})


@list_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    players = load_players()
    names = [p["name"] for p in players.values() if p["gid"] == gid]
    await list_m.finish("本群玩家：" + ("、".join(names) if names else "暂无"))


# 签到
daily_m = on_keyword({"签到"})


@daily_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = _event_ids(event)
    p = get_player(uid, gid, name)
    if p["counters"]["signed"]:
        await daily_m.finish("今天已签到过了")
    dust, stat = gacha10_to_dust()
    p["dust"] += dust
    p["counters"]["signed"] = True
    put_player(p)
    await daily_m.finish(
        f"签到成功：5★x{stat['5★']} 4★x{stat['4★']} 3★x{stat['3★']} → 粉尘+{dust}"
    )


# 十连
gacha_m = on_keyword({"十连", "抽卡"})


@gacha_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = _event_ids(event)
    p = get_player(uid, gid, name)
    if p["diamond"] < 3000:
        await gacha_m.finish(f"钻石不足，当前{p['diamond']}")
    p["diamond"] -= 3000
    dust, stat = gacha10_to_dust()
    p["dust"] += dust
    put_player(p)
    await gacha_m.finish(
        f"十连完成：5★{stat['5★']} 4★{stat['4★']} 3★{stat['3★']} → 粉尘+{dust}"
    )


# 精炼
refine_m = on_regex(r"^精炼\s*([123])$")


@refine_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = _event_ids(event)
    p = get_player(uid, gid, name)
    idx = int(re.match(r"^精炼\s*([123])$", _text(event)).group(1))
    cur = p["weapon"]["slots"][idx - 1]
    if cur >= 4:
        await refine_m.finish("该槽位已是S")
    nxt = cur + 1
    cost = refine_cost(nxt)
    if p["dust"] < cost:
        await refine_m.finish(f"粉尘不足，需要{cost}")
    p["dust"] -= cost
    p["weapon"]["slots"][idx - 1] = nxt
    put_player(p)
    await refine_m.finish(
        f"精炼成功：当前段位{slots_to_rank(p['weapon']['slots'])}｜评分{score_of_slots(p['weapon']['slots'])}"
    )


# 远征
wild_m = on_keyword({"远征", "打野"})


@wild_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = _event_ids(event)
    p = get_player(uid, gid, name)
    c = p["counters"]
    if c["free_explore_used"] < 2:
        c["free_explore_used"] += 1
    elif p["ticket"] > 0:
        p["ticket"] -= 1
    elif p["diamond"] >= 300:
        p["diamond"] -= 300
    else:
        await wild_m.finish("远征需要每日2次免费/探索券/钻石300")
    dia = random.randint(30, 60)
    dus = random.randint(5, 15)
    p["diamond"] += dia
    p["dust"] += dus
    put_player(p)
    await wild_m.finish(f"远征完成：钻石+{dia} 粉尘+{dus}")


# 对战
pvp_m = on_regex(r"^(对战|pk)")


@pvp_m.handle()
async def _(event: MessageEvent, bot: Bot):
    gid = str(getattr(event, "group_id", 0))
    uid, gid, name = _event_ids(event)
    target = _first_at(event)
    if not target or target == uid:
        await pvp_m.finish("用法：对战 @某人")
    a = get_player(uid, gid, name)
    b_info = await bot.get_group_member_info(group_id=int(gid), user_id=int(target))
    b = get_player(target, gid, b_info.get("card") or b_info.get("nickname") or target)
    log, w = simulate_duel(
        a["name"], derive_internal_stats(a), b["name"], derive_internal_stats(b)
    )
    await pvp_m.finish(log)


# BOSS信息
boss_info_m = on_keyword({"boss", "BOSS", "世界boss", "世界BOSS"})


@boss_info_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    b = get_boss(gid)
    await boss_info_m.finish(
        f"【BOSS】{b['name']} HP {b['hp']}/{b['hp_max']} 已击杀:{'是' if b['killed'] else '否'}"
    )


# 出刀
boss_hit_m = on_keyword({"出刀", "打boss", "攻打boss"})


@boss_hit_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    uid, gid, name = _event_ids(event)
    p = get_player(uid, gid, name)
    if p["counters"]["boss_hits"] >= 3:
        await boss_hit_m.finish("今天出刀次数已用完")
    b = get_boss(gid)
    if b["killed"]:
        await boss_hit_m.finish("今日BOSS已击杀")
    p_stat = derive_internal_stats(p)
    boss_stat = {
        "ATK": b["atk"],
        "DEF": b["def"],
        "HP": b["hp"],
        "SPD": b["spd"],
        "CRIT": b["crit"],
    }
    log, w = simulate_duel(p["name"], p_stat, b["name"], boss_stat)
    last_left = None
    for line in log.splitlines()[::-1]:
        m = re.search(rf"{b['name']} 剩 (\d+)", line)
        if m:
            last_left = int(m.group(1))
            break
    b_left = last_left if last_left is not None else (0 if w == p["name"] else b["hp"])
    dealt = max(0, b["hp"] - b_left)
    b["hp"] = max(0, b_left)
    if b["hp"] == 0:
        b["killed"] = True
    b["board"][uid] = b["board"].get(uid, 0) + dealt
    put_boss(b)
    dia = 20 + dealt // 20
    dus = 10 + dealt // 30
    p["diamond"] += dia
    p["dust"] += dus
    p["counters"]["boss_hits"] += 1
    put_player(p)
    await boss_hit_m.finish(
        f"{p['name']} 对BOSS造成{dealt}伤害 剩余{b['hp']} 奖励:钻石+{dia} 粉尘+{dus}"
    )
