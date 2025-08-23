# -*- coding: utf-8 -*-
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, Bot
from ..models import get_player
from ..logic_battle import derive_internal_stats, simulate_duel
from ..utils import ids_of, first_at

pvp_m = on_regex(r"^(对战|pk)")


@pvp_m.handle()
async def _(event: MessageEvent, bot: Bot):
    gid = str(getattr(event, "group_id", 0))
    uid, gid, name = ids_of(event)
    target = first_at(event)
    if not target or target == uid:
        await pvp_m.finish("用法：对战 @某人")
    a = get_player(uid, gid, name)
    info = await bot.get_group_member_info(group_id=int(gid), user_id=int(target))
    b = get_player(target, gid, info.get("card") or info.get("nickname") or target)
    log, _ = simulate_duel(
        a["name"], derive_internal_stats(a), b["name"], derive_internal_stats(b)
    )
    await pvp_m.finish(log)
