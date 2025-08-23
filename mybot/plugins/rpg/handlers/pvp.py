# -*- coding: utf-8 -*-
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, Bot

from ..logic_battle import derive_internal_stats, simulate_duel_with_skills
from ..logic_skill import Entity, equip_skills_for_player
from ..models.player import get_player
from ..utils import ids_of, first_at

pvp_m = on_regex(r"^(对战|pk)")


@pvp_m.handle()
async def _(event: MessageEvent, bot: Bot):
    gid = str(getattr(event, "group_id", 0))
    uid, gid, name = ids_of(event)

    target = first_at(event)
    if not target or target == uid:
        await pvp_m.finish("用法：对战 @某人")

    # 加载双方玩家
    a = get_player(uid, gid, name)
    info = await bot.get_group_member_info(group_id=int(gid), user_id=int(target))
    b = get_player(target, gid, info.get("card") or info.get("nickname") or target)

    a_stat = derive_internal_stats(a)
    b_stat = derive_internal_stats(b)

    # 为实体装配技能（基于玩家数据/武器评分）
    def equipA(ent: Entity):
        equip_skills_for_player(a, ent)

    def equipB(ent: Entity):
        equip_skills_for_player(b, ent)

    log, winner = simulate_duel_with_skills(
        a_name=a["name"],
        a_stat=a_stat,
        b_name=b["name"],
        b_stat=b_stat,
        equip_A=equipA,
        equip_B=equipB,
    )

    await pvp_m.finish(log)
