# -*- coding: utf-8 -*-
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_fullmatch

from ..logic_economy import gacha10_to_dust
from ..models import get_player, put_player
from ..utils import ids_of

daily_m = on_fullmatch("签到")

@daily_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    if p.counters.signed:
        await daily_m.finish("今天已签到过了")
    dust, stat = gacha10_to_dust()
    p.dust += dust
    p.counters.signed = True
    put_player(p)
    await daily_m.finish(
        f"十连完成：{stat}\n总计获得粉尘：{dust}"
    )
