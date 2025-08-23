# mybot/plugins/rpg/handlers/boss.py
# -*- coding: utf-8 -*-
import re
from nonebot import on_keyword
from nonebot.plugin.on import on_fullmatch
from nonebot.adapters.onebot.v11 import MessageEvent

from ..models import get_boss, put_boss, get_player, put_player
from ..logic_battle import simulate_duel_with_skills
from ..utils import ids_of

# 技能装配：优先使用“配表技能”，若未启用则回退到内置
try:
    from ..skill_config import equip_skills_for_player_from_cfg as equip_skills_for_player  # type: ignore
except Exception:
    from ..logic_skill import equip_skills_for_player  # 旧版内置

boss_info_m = on_fullmatch({"boss", "BOSS", "世界boss", "世界BOSS"})
boss_hit_m = on_fullmatch({"出刀", "打boss", "攻打boss"})


@boss_info_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    b = get_boss(gid)
    pct = int(100 * b.hp / b.hp_max) if b.hp_max else 0

    # ...排行榜处理...
    if b.board:
        rank_list = sorted(b.board.items(), key=lambda x: x[1], reverse=True)
        rank_str = ""
        for i, (uid, dmg) in enumerate(rank_list[:10]):
            player = get_player(uid, gid, None)
            pname = getattr(player, "name", uid)
            rank_str += f"{i+1}. {pname}：{dmg}伤害\n"
        rank_str = f"\n【伤害排行榜】\n{rank_str.strip()}"
    else:
        rank_str = "\n【伤害排行榜】\n暂无出刀记录"

    await boss_info_m.finish(
        f"【BOSS】{b.name}  HP {b.hp}/{b.hp_max}（{pct}%）  已击杀：{'是' if b.killed else '否'}"
        f"{rank_str}"
    )


@boss_hit_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    uid, gid, name = ids_of(event)

    p = get_player(uid, gid, name)
    if p.counters.boss_hits >= 3:
        await boss_hit_m.finish("今天出刀次数已用完（3/3）")

    b = get_boss(gid)
    if b.killed or b.hp <= 0:
        await boss_hit_m.finish("今日BOSS已击杀")
    before = b.hp
    print("【调试】Boss血量：", before)

    # 直接用 boss 名称作为怪物ID，要求 monsters.yaml 里有同名boss定义
    result, logs = simulate_duel_with_skills(p, monster_id=b.name, boss_hp=b.hp)
    log_str = "\n".join(logs)

    # 从战报回收本刀伤害
    last_left = None
    for line in reversed(log_str.splitlines()):
        m = re.search(
            rf"对 {re.escape(b.name)} 造成了 .*?（剩余HP[:：]?\s*(\d+)\）", line
        )
        if m:
            last_left = int(m.group(1))
            break
    boss_left_hp = last_left if last_left is not None else before
    damage_dealt = max(0, before - boss_left_hp)
    print("【调试】本刀伤害：", damage_dealt)

    # 更新Boss与排行榜
    b.hp = max(0, boss_left_hp)
    if b.hp == 0:
        b.killed = True
    b.board[uid] = b.board.get(uid, 0) + damage_dealt
    put_boss(b)

    # 奖励结算
    dia = 20 + damage_dealt // 20
    dus = 10 + damage_dealt // 30
    p.diamond += dia
    p.dust += dus
    p.counters.boss_hits += 1
    put_player(p)

    await boss_hit_m.finish(
        f"{p.name} 对BOSS造成 {damage_dealt} 伤害\n"
        f"BOSS 剩余：{b.hp}/{b.hp_max}\n"
        f"奖励：钻石 +{dia}  粉尘 +{dus}（今日出刀 {p.counters.boss_hits}/3）\n"
        f"{'-'*20}\n{log_str}"
    )
