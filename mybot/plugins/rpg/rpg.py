# mybot/plugins/rpg.py
# -*- coding: utf-8 -*-
"""
RPG Bot（JSON 存档版，能跑的骨架）
- 战斗：自动出招，一次性完整战报
- 存取：JSON + 简易锁
- 远征：入场=抽卡资源（探索券），每天免费2次
- 出刀：世界BOSS，每人每天3次
- 抽卡：十连只产粉尘
- 装备升级：武器精炼（CCC→SSS，权重1/2/3）
- 信息查询：面板/群内玩家一览
"""
from __future__ import annotations
import os, json, time, random, threading
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

from nonebot import on_command
from nonebot.rule import to_me
from nonebot.params import ArgPlainText
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message

# --------------- 常量与数据目录 -----------------
DATA_DIR = os.path.join(os.getcwd(), "data")
PLAYERS_JSON = os.path.join(DATA_DIR, "players.json")
BOSS_JSON = os.path.join(DATA_DIR, "boss.json")

os.makedirs(DATA_DIR, exist_ok=True)

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


# --------------- 数据模型 -----------------
def today_tag() -> str:
    # 用日期做“每日次数”的分隔
    return time.strftime("%Y-%m-%d", time.localtime())


def _default_player(uid: str, gid: str, name: str) -> Dict:
    # 初始角色：Lv1、未分配点0、武器CCC(1/1/1)
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
        "ticket": 0,  # ticket=探索券(抽卡资源)
        "counters": {  # 每日计数
            "daily_date": today_tag(),
            "free_explore_used": 0,  # 远征每日免费2次
            "boss_hits": 0,  # 出刀每日3次
            "signed": False,
        },
    }


def _default_boss(gid: str) -> Dict:
    # 群维度 BOSS（每日一个）
    return {
        "gid": gid,
        "boss_date": today_tag(),
        "name": "远古巨像",
        "hp": 3000,  # 可以根据活跃度做自适应，先给定值
        "hp_max": 3000,
        "atk": 50,
        "def": 15,
        "spd": 10,
        "crit": 10,
        "board": {},  # uid -> 累计伤害
        "killed": False,
    }


# --------------- 存取封装 -----------------
def load_players() -> Dict[str, Dict]:
    return _load_json(PLAYERS_JSON, {})


def save_players(players: Dict[str, Dict]):
    _save_json(PLAYERS_JSON, players)


def load_boss_map() -> Dict[str, Dict]:
    return _load_json(BOSS_JSON, {})


def save_boss_map(boss_map: Dict[str, Dict]):
    _save_json(BOSS_JSON, boss_map)


def get_player(uid: str, gid: str, name: str) -> Dict:
    players = load_players()
    key = f"{gid}:{uid}"
    p = players.get(key)
    if not p:
        p = _default_player(uid, gid, name)
        players[key] = p
        save_players(players)
    else:
        # 刷新每日计数
        if p["counters"].get("daily_date") != today_tag():
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
    if (not b) or (b.get("boss_date") != today_tag()):
        b = _default_boss(gid)
        bm[gid] = b
        save_boss_map(bm)
    return b


def put_boss(b: Dict):
    bm = load_boss_map()
    bm[b["gid"]] = b
    save_boss_map(bm)


# --------------- 通用工具 -----------------
def score_of_slots(slots: List[int]) -> int:
    # 权重 1/2/3
    return int(slots[0] * 1 + slots[1] * 2 + slots[2] * 3)


def slots_to_rank(slots: List[int]) -> str:
    m = {1: "C", 2: "B", 3: "A", 4: "S"}
    return "".join(m[x] for x in slots)


def refine_cost(next_val: int) -> int:
    # C->B:100; B->A:300; A->S:900
    if next_val == 2:
        return 100
    if next_val == 3:
        return 300
    if next_val == 4:
        return 900
    return 999999


def gacha10_to_dust() -> Tuple[int, Dict[str, int]]:
    # 3★ 77% → 30; 4★ 20% → 120; 5★ 3% → 600
    stars = []
    for _ in range(10):
        r = random.random()
        if r < 0.03:
            stars.append(5)
        elif r < 0.23:
            stars.append(4)
        else:
            stars.append(3)
    dust = sum(600 if s == 5 else 120 if s == 4 else 30 for s in stars)
    stat = {"5★": stars.count(5), "4★": stars.count(4), "3★": stars.count(3)}
    return dust, stat


# ----------- 内在属性（隐藏，不对外显示） -----------
def derive_internal_stats(p: Dict) -> Dict[str, float]:
    Lv = p["level"]
    pts = p["points"]
    slots = p["weapon"]["slots"]
    score = score_of_slots(slots)
    hp_base = 80 + 10 * Lv
    atk_base = 6 + 2 * score + Lv
    def_base = 4 + 1 * Lv
    spd_base = 8 + (Lv // 2)
    crit_base = 10
    # 加点
    ATK = atk_base + 2 * pts["str"]
    DEF = def_base + 1.5 * pts["def"]
    HP = hp_base + 12 * pts["hp"]
    SPD = spd_base + 0.6 * pts["agi"]
    CRIT = min(30, crit_base + 0.8 * pts["crit"])
    return {"ATK": ATK, "DEF": DEF, "HP": HP, "SPD": SPD, "CRIT": CRIT}


def damage_calc(
    atk: float, dfn: float, mult: float, bonus_crit: int = 0
) -> Tuple[int, bool]:
    base = max(1.0, atk - 0.5 * dfn)
    roll = random.uniform(0.95, 1.05)
    dmg = max(1, int(base * roll * mult))
    crit_chance = min(100, 10 + bonus_crit)  # 基础10%（内在会覆盖，这里当额外加成）
    if random.randint(1, 100) <= crit_chance:
        return int(dmg * 1.5), True
    return dmg, False


# 自动出招AI（基于期望伤害的简单策略）
def choose_skill(expect_base: int, cds: Dict[str, int]) -> Tuple[str, float, int]:
    """
    返回 (技能名, 倍率, 额外暴击%)
    cd规则：重击cd=2；迅击cd=1；普攻=0
    """
    # 估算是否可击杀的逻辑可在完整战斗里做，这里给出优先级：
    order = []
    if cds.get("重击", 0) <= 0:
        order.append(("重击", 1.8, 0, 2))
    if cds.get("迅击", 0) <= 0:
        order.append(("迅击", 0.85, 10, 1))
    order.append(("普攻", 1.0, 0, 0))
    return order[0][0], order[0][1], order[0][2]


# --------------- 战斗模拟（一次性输出战报） -----------------
def simulate_duel(
    a_name: str,
    a_stat: Dict[str, float],
    b_name: str,
    b_stat: Dict[str, float],
    seed: Optional[int] = None,
    max_rounds: int = 30,
) -> Tuple[str, str]:
    """
    返回 (战报文本, 胜者名)
    """
    if seed is None:
        seed = int(time.time() * 1000) & 0xFFFFFFFF
    random.seed(seed)

    a_hp = int(a_stat["HP"])
    b_hp = int(b_stat["HP"])
    a_spd = a_stat["SPD"]
    b_spd = b_stat["SPD"]
    a_atk = a_stat["ATK"]
    b_atk = b_stat["ATK"]
    a_def = a_stat["DEF"]
    b_def = b_stat["DEF"]

    turn = a_name if a_spd >= b_spd else b_name
    a_cds = {"重击": 0, "迅击": 0}
    b_cds = {"重击": 0, "迅击": 0}

    log = [f"【对战开始】先手：{turn}"]
    rounds = 0
    while a_hp > 0 and b_hp > 0 and rounds < max_rounds:
        rounds += 1
        # 先手出手者
        for actor in (turn, (b_name if turn == a_name else a_name)):
            if a_hp <= 0 or b_hp <= 0:
                break
            if actor == a_name:
                expect = max(1, int(a_atk - 0.5 * b_def))
                sname, mult, bcrit = choose_skill(expect, a_cds)
                dmg, crit = damage_calc(a_atk, b_def, mult, bcrit)
                b_hp -= dmg
                a_cds["重击"] = max(0, a_cds["重击"] - 1)
                a_cds["迅击"] = max(0, a_cds["迅击"] - 1)
                if sname == "重击":
                    a_cds["重击"] = 2
                if sname == "迅击":
                    a_cds["迅击"] = 1
                log.append(
                    f"R{rounds}: {a_name} {sname} → {dmg}{'（暴击）' if crit else ''} | {b_name} 剩 {max(0,b_hp)}"
                )
            else:
                expect = max(1, int(b_atk - 0.5 * a_def))
                sname, mult, bcrit = choose_skill(expect, b_cds)
                dmg, crit = damage_calc(b_atk, a_def, mult, bcrit)
                a_hp -= dmg
                b_cds["重击"] = max(0, b_cds["重击"] - 1)
                b_cds["迅击"] = max(0, b_cds["迅击"] - 1)
                if sname == "重击":
                    b_cds["重击"] = 2
                if sname == "迅击":
                    b_cds["迅击"] = 1
                log.append(
                    f"R{rounds}: {b_name} {sname} → {dmg}{'（暴击）' if crit else ''} | {a_name} 剩 {max(0,a_hp)}"
                )
        # 下回合先手
        turn = b_name if turn == a_name else a_name

    if a_hp <= 0 and b_hp <= 0:
        winner = a_name  # 平手时给先手
    elif a_hp <= 0:
        winner = b_name
    elif b_hp <= 0:
        winner = a_name
    else:
        # 回合上限，血多者胜
        winner = a_name if a_hp >= b_hp else b_name

    log.append(f"【结果】胜者：{winner}（{rounds} 回合） seed={seed}")
    return "\n".join(log[:120]), winner  # 控制长度


# --------------- 指令：创建/面板/列表 -----------------
start_cmd = on_command("rpg.start", priority=5, block=True)
rename_cmd = on_command("rpg.rename", priority=5, block=True)
profile_cmd = on_command("rpg.profile", priority=5, block=True)
list_cmd = on_command("rpg.list", priority=5, block=True)


@start_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: str = ArgPlainText("arg")):
    uid, gid = str(event.user_id), str(event.group_id)
    name = event.sender.card or event.sender.nickname
    p = get_player(uid, gid, name)
    if arg.strip():
        p["weapon"]["name"] = arg.strip()[:20]
        put_player(p)
    slots = p["weapon"]["slots"]
    await start_cmd.finish(
        f"创建/加载成功！\n"
        f"武器：{p['weapon']['name']}（{slots_to_rank(slots)}｜评分{score_of_slots(slots)}）\n"
        f"等级：{p['level']}  未分配点：{p['unspent']}\n"
        f"粉尘：{p['dust']}  钻石：{p['diamond']}  探索券：{p['ticket']}  女神之泪：{p['tear']}\n"
        f"可用：/rpg.profile、/rpg.gacha10、/rpg.refine 1|2|3、/rpg.wild、/rpg.boss.hit"
    )


@rename_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: str = ArgPlainText("arg")):
    uid, gid = str(event.user_id), str(event.group_id)
    p = get_player(uid, gid, event.sender.card or event.sender.nickname)
    new = arg.strip()[:20]
    if not new:
        await rename_cmd.finish("用法：/rpg.rename 新武器名")
    p["weapon"]["name"] = new
    put_player(p)
    await rename_cmd.finish(f"已改名：{new}")


@profile_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    uid, gid = str(event.user_id), str(event.group_id)
    p = get_player(uid, gid, event.sender.card or event.sender.nickname)
    slots = p["weapon"]["slots"]
    await profile_cmd.finish(
        f"【面板】{p['name']} Lv.{p['level']}\n"
        f"武器：{p['weapon']['name']}（{slots_to_rank(slots)}｜评分{score_of_slots(slots)}）\n"
        f"加点：力{p['points']['str']} 防{p['points']['def']} 血{p['points']['hp']} 敏{p['points']['agi']} 暴{p['points']['crit']}\n"
        f"未分配点：{p['unspent']}\n"
        f"粉尘：{p['dust']}  钻石：{p['diamond']}  探索券：{p['ticket']}  女神之泪：{p['tear']}\n"
        f"今日：远征免费{p['counters']['free_explore_used']}/2；出刀{p['counters']['boss_hits']}/3；签到：{'已领' if p['counters']['signed'] else '未领'}"
    )


@list_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    gid = str(event.group_id)
    players = load_players()
    names = []
    for key, p in players.items():
        if p["gid"] == gid:
            names.append(p["name"])
    if not names:
        await list_cmd.finish("本群暂无玩家。使用 /rpg.start 开始。")
    await list_cmd.finish("本群玩家一览：\n" + "、".join(names[:50]))


# --------------- 指令：抽卡/签到/精炼 -----------------
gacha_cmd = on_command("rpg.gacha10", priority=5, block=True)
daily_cmd = on_command("rpg.daily", priority=5, block=True)
refine_cmd = on_command("rpg.refine", priority=5, block=True)


@gacha_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    uid, gid = str(event.user_id), str(event.group_id)
    p = get_player(uid, gid, event.sender.card or event.sender.nickname)
    # 十连成本：3000 钻
    if p["diamond"] < 3000:
        await gacha_cmd.finish(
            f"钻石不足（需要3000，当前{p['diamond']}）。可通过 /rpg.wild 或 BOSS 获得。"
        )
    p["diamond"] -= 3000
    dust, stat = gacha10_to_dust()
    p["dust"] += dust
    put_player(p)
    await gacha_cmd.finish(
        f"十连完成：5★x{stat['5★']} 4★x{stat['4★']} 3★x{stat['3★']} → 获得粉尘 {dust}\n当前粉尘：{p['dust']}"
    )


@daily_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    uid, gid = str(event.user_id), str(event.group_id)
    p = get_player(uid, gid, event.sender.card or event.sender.nickname)
    if p["counters"]["signed"]:
        await daily_cmd.finish("今天已经领过了。")
    dust, stat = gacha10_to_dust()  # 免费十连 → 只给粉尘
    p["dust"] += dust
    p["counters"]["signed"] = True
    put_player(p)
    await daily_cmd.finish(
        f"签到成功！免费十连：5★x{stat['5★']} 4★x{stat['4★']} 3★x{stat['3★']} → 粉尘 +{dust}\n当前粉尘：{p['dust']}"
    )


@refine_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: str = ArgPlainText("arg")):
    uid, gid = str(event.user_id), str(event.group_id)
    p = get_player(uid, gid, event.sender.card or event.sender.nickname)
    try:
        idx = int(arg.strip())
        if idx not in (1, 2, 3):
            raise ValueError()
    except:
        await refine_cmd.finish("用法：/rpg.refine 1|2|3  （对应三槽，权重1/2/3）")
    slots = p["weapon"]["slots"]
    cur = slots[idx - 1]
    if cur >= 4:
        await refine_cmd.finish("该槽位已是 S，无法继续。")
    nxt = cur + 1
    cost = refine_cost(nxt)
    if p["dust"] < cost:
        await refine_cmd.finish(f"粉尘不足，需要 {cost}，当前 {p['dust']}")
    p["dust"] -= cost
    slots[idx - 1] = nxt
    put_player(p)
    await refine_cmd.finish(
        f"精炼成功：槽位{idx} {['C','B','A','S'][cur-1]}→{['C','B','A','S'][nxt-1]}\n"
        f"当前段位：{slots_to_rank(slots)}｜评分 {score_of_slots(slots)}｜粉尘 {p['dust']}"
    )


# --------------- 指令：远征（每天免费2次） -----------------
wild_cmd = on_command("rpg.wild", priority=5, block=True)


@wild_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    uid, gid = str(event.user_id), str(event.group_id)
    p = get_player(uid, gid, event.sender.card or event.sender.nickname)
    c = p["counters"]
    # 免费票：每天2次；否则消耗探索券（ticket）或钻石
    if c["free_explore_used"] < 2:
        c["free_explore_used"] += 1
        ticket_used = "(免费)"
    elif p["ticket"] > 0:
        p["ticket"] -= 1
        ticket_used = "(消耗探索券1)"
    elif p["diamond"] >= 300:
        p["diamond"] -= 300
        ticket_used = "(消耗钻石300)"
    else:
        await wild_cmd.finish(
            "远征需要：每日免费2次/探索券/钻石300（三选一）。当前不足。"
        )
    # 奖励：钻石 30~60，粉尘 5~15，少许经验
    dia = random.randint(30, 60)
    dus = random.randint(5, 15)
    p["diamond"] += dia
    p["dust"] += dus
    # 简单经验&升级
    p["level"] += 0  # 可按需要增加经验系统；这里先略
    put_player(p)
    await wild_cmd.finish(
        f"远征完成 {ticket_used}：钻石 +{dia}，粉尘 +{dus}\n当前：钻石 {p['diamond']}｜粉尘 {p['dust']}｜今日免费 {p['counters']['free_explore_used']}/2"
    )


# --------------- 指令：PVP（一次性战斗日志 & 结果） ---------------
pvp_cmd = on_command("rpg.pvp", priority=5, block=True)


def _first_at(event: GroupMessageEvent) -> Optional[str]:
    for seg in event.message:
        if seg.type == "at" and "qq" in seg.data:
            return str(seg.data["qq"])
    return None


@pvp_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    gid = str(event.group_id)
    uid = str(event.user_id)
    target = _first_at(event)
    if not target or target == uid:
        await pvp_cmd.finish("用法：/rpg.pvp @对手")
    # 加载双方
    a = get_player(uid, gid, event.sender.card or event.sender.nickname)
    b_info = await bot.get_group_member_info(group_id=int(gid), user_id=int(target))
    b = get_player(target, gid, b_info.get("card") or b_info.get("nickname") or target)
    # 内在属性
    a_stat = derive_internal_stats(a)
    b_stat = derive_internal_stats(b)
    # 模拟
    log, winner = simulate_duel(a["name"], a_stat, b["name"], b_stat)
    await pvp_cmd.finish(log)


# --------------- 指令：世界BOSS（出刀=每天3次） ---------------
boss_info_cmd = on_command("rpg.boss.info", priority=5, block=True)
boss_hit_cmd = on_command("rpg.boss.hit", priority=5, block=True)


@boss_info_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    gid = str(event.group_id)
    b = get_boss(gid)
    pct = int(100 * b["hp"] / b["hp_max"]) if b["hp_max"] else 0
    await boss_info_cmd.finish(
        f"【世界BOSS】{b['name']}  HP {b['hp']}/{b['hp_max']}（{pct}%）\n今日已被击杀：{'是' if b['killed'] else '否'}"
    )


@boss_hit_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    gid = str(event.group_id)
    uid = str(event.user_id)
    name = event.sender.card or event.sender.nickname
    p = get_player(uid, gid, name)
    if p["counters"]["boss_hits"] >= 3:
        await boss_hit_cmd.finish("今天出刀次数已用完（3/3）。")
    b = get_boss(gid)
    if b["killed"]:
        await boss_hit_cmd.finish("今日BOSS已击杀，明日再来。")
    # 用玩家 vs BOSS 进行一次完整战斗，记录对BOSS造成的总伤害（按战报累积）
    # 简化：用一次“纯伤害对打”，并把BOSS视为另一名选手
    p_stat = derive_internal_stats(p)
    boss_stat = {
        "ATK": b["atk"],
        "DEF": b["def"],
        "HP": b["hp"],
        "SPD": b["spd"],
        "CRIT": b["crit"],
    }
    log, winner = simulate_duel(p["name"], p_stat, b["name"], boss_stat)
    # 解析玩家造成的总伤害（通过开局HP差/剩余判断近似）
    # 更严谨：直接重写一个“打木桩”函数；这里简单：用原hp_max - 剩余hp 作为受伤
    lines = log.splitlines()
    # 尝试从 boss_stat.HP 与末行“剩”推断
    # 我们直接重新计算：开局BOSS HP - 现在BOSS HP
    # 从 boss_map 读最新BOSS，再比较减血
    before = b["hp"]
    # 从战报末几行抓最后一次“BOSS 剩 X”，否则根据胜负判断
    import re

    last_left = None
    for line in lines[::-1]:
        m = re.search(rf"{b['name']} 剩 (\d+)", line)
        if m:
            last_left = int(m.group(1))
            break
    b_left = (
        last_left if last_left is not None else (0 if winner == p["name"] else before)
    )
    dealt = max(0, before - b_left)

    # 更新BOSS
    b["hp"] = max(0, b_left)
    if b["hp"] == 0:
        b["killed"] = True
    # 记榜
    b["board"][uid] = b["board"].get(uid, 0) + dealt
    put_boss(b)

    # 奖励：即时给少量钻石/粉尘
    dia = 20 + dealt // 20
    dus = 10 + dealt // 30
    p["diamond"] += dia
    p["dust"] += dus
    p["counters"]["boss_hits"] += 1
    put_player(p)

    await boss_hit_cmd.finish(
        f"{p['name']} 对 BOSS 造成 {dealt} 伤害\n"
        f"BOSS 剩余：{b['hp']}/{b['hp_max']}\n"
        f"奖励：钻石 +{dia} 粉尘 +{dus}（今日出刀 {p['counters']['boss_hits']}/3）"
    )
