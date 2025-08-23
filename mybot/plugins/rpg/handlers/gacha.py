# -*- coding: utf-8 -*-

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_fullmatch

from ..logic_economy import gacha10_to_dust
from ..models import get_player, put_player
from ..utils import ids_of

gacha_m = on_fullmatch(("十连", "抽卡"))

@gacha_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    if p.diamond < 1500:
        await gacha_m.finish(f"钻石不足，当前{p.diamond}")
    p.diamond -= 1500
    dust, stat = gacha10_to_dust()
    p.dust += dust
    put_player(p)
    await gacha_m.finish(
        f"十连完成：{stat}\n总计获得粉尘：{dust},剩余钻石：{p.diamond}"
    )
