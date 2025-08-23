# mybot/plugins/rpg/handlers/boss.py
# -*- coding: utf-8 -*-
import re
from nonebot import on_keyword
from nonebot.adapters.onebot.v11 import MessageEvent

from ..models import get_boss, put_boss, get_player, put_player
from ..logic_battle import simulate_duel_with_skills
from ..utils import ids_of

# 技能装配：优先使用“配表技能”，若未启用则回退到内置
try:
    from ..skill_config import equip_skills_for_player_from_cfg as equip_skills_for_player  # type: ignore
except Exception:
    from ..logic_skill import equip_skills_for_player  # 旧版内置

boss_info_m = on_keyword({"boss", "BOSS", "世界boss", "世界BOSS"})
boss_hit_m = on_keyword({"出刀", "打boss", "攻打boss"})


@boss_info_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    b = get_boss(gid)
    pct = int(100 * b.hp / b.hp_max) if b.hp_max else 0
    await boss_info_m.finish(
        f"【BOSS】{b.name}  HP {b.hp}/{b.hp_max}（{pct}%）  已击杀：{'是' if b.killed else '否'}"
    )


@boss_hit_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    uid, gid, name = ids_of(event)

    p = get_player(uid, gid, name)
    if p.counters.boss_hits >= 3:
        await boss_hit_m.finish("今天出刀次数已用完（3/3）")

    b = get_boss(gid)
    if b.killed:
        await boss_hit_m.finish("今日BOSS已击杀")

    # 直接用 boss 名称作为怪物ID，要求 monsters.yaml 里有同名boss定义
    log, winner = simulate_duel_with_skills(p, monster_id=b.name)

    # 从战报回收本刀伤害
    before = b.hp
    last_left = None
    for line in reversed(log.splitlines()):
        m = re.search(rf"{b.name}.*剩[余:]?\s*(\d+)", line)
        if m:
            last_left = int(m.group(1))
            break
    b_left = last_left if last_left is not None else (0 if winner == p.name else before)
    dealt = max(0, before - b_left)

    # 更新Boss与排行榜
    b.hp = max(0, b_left)
    if b.hp == 0:
        b.killed = True
    b.board[uid] = b.board.get(uid, 0) + dealt
    put_boss(b)

    # 奖励结算
    dia = 20 + dealt // 20
    dus = 10 + dealt // 30
    p.diamond += dia
    p.dust += dus
    p.counters.boss_hits += 1
    put_player(p)

    await boss_hit_m.finish(
        f"{p.name} 对BOSS造成 {dealt} 伤害\n"
        f"BOSS 剩余：{b.hp}/{b.hp_max}\n"
        f"奖励：钻石 +{dia}  粉尘 +{dus}（今日出刀 {p.counters.boss_hits}/3）\n"
        f"{'-'*20}\n{log}"
    )
