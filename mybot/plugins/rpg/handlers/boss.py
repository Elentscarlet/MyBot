# -*- coding: utf-8 -*-
import re
from nonebot import on_keyword
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models.player import get_player
from ..logic_battle import derive_internal_stats, simulate_duel_with_skills
from ..logic_skill import Entity, equip_skills_for_player, thorns_passive
from ..utils import ids_of

boss_info_m = on_keyword({"boss", "BOSS", "世界boss", "世界BOSS"})
boss_hit_m = on_keyword({"出刀", "打boss", "攻打boss"})


@boss_info_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    b = get_boss(gid)
    pct = int(100 * b["hp"] / b["hp_max"]) if b["hp_max"] else 0
    await boss_info_m.finish(
        f"【BOSS】{b['name']}  HP {b['hp']}/{b['hp_max']}（{pct}%）  已击杀：{'是' if b['killed'] else '否'}"
    )


@boss_hit_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    uid, gid, name = ids_of(event)

    p = get_player(uid, gid, name)
    if p["counters"]["boss_hits"] >= 3:
        await boss_hit_m.finish("今天出刀次数已用完（3/3）")

    b = get_boss(gid)
    if b["killed"]:
        await boss_hit_m.finish("今日BOSS已击杀")

    # 玩家与BOSS面板
    p_stat = derive_internal_stats(p)
    boss_stat = {
        "ATK": b["atk"],
        "DEF": b["def"],
        "HP": b["hp"],
        "SPD": b["spd"],
        "CRIT": b["crit"],
    }

    # 装备技能（玩家按评分装，BOSS给个荆棘被动示例）
    def equipP(ent: Entity):
        equip_skills_for_player(p, ent)

    def equipB(ent: Entity):
        ent.skills = [thorns_passive]  # 你可以根据需要给BOSS更多技能/被动

    # 模拟战斗（一次性战报）
    log, winner = simulate_duel_with_skills(
        a_name=p["name"],
        a_stat=p_stat,
        b_name=b["name"],
        b_stat=boss_stat,
        equip_A=equipP,
        equip_B=equipB,
    )

    # 从战报中抓取 BOSS 最后“剩 X”来计算本刀伤害（简单可靠）
    before = b["hp"]
    last_left = None
    for line in log.splitlines()[::-1]:
        m = re.search(rf"{b['name']} 剩 (\d+)", line)
        if m:
            last_left = int(m.group(1))
            break
    b_left = (
        last_left if last_left is not None else (0 if winner == p["name"] else before)
    )
    dealt = max(0, before - b_left)

    # 更新BOSS与排行榜
    b["hp"] = max(0, b_left)
    if b["hp"] == 0:
        b["killed"] = True
    b["board"][uid] = b["board"].get(uid, 0) + dealt
    put_boss(b)

    # 奖励结算
    dia = 20 + dealt // 20
    dus = 10 + dealt // 30
    p["diamond"] += dia
    p["dust"] += dus
    p["counters"]["boss_hits"] += 1
    p.save()

    await boss_hit_m.finish(
        f"{p['name']} 对BOSS造成 {dealt} 伤害\n"
        f"BOSS 剩余：{b['hp']}/{b['hp_max']}\n"
        f"奖励：钻石 +{dia}  粉尘 +{dus}（今日出刀 {p['counters']['boss_hits']}/3）"
    )
