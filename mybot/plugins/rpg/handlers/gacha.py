# -*- coding: utf-8 -*-
from nonebot import on_keyword
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models import get_player, put_player
from ..logic_economy import gacha10_to_dust
from ..utils import ids_of

gacha_m = on_keyword({"十连", "抽卡"})


@gacha_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    if p.diamond < 3000:
        await gacha_m.finish(f"钻石不足，当前{p.diamond}")
    p.diamond -= 3000
    dust, stat = gacha10_to_dust()
    p.dust += dust
    put_player(p)
    await gacha_m.finish(
        f"十连完成：5★{stat['5★']} 4★{stat['4★']} 3★{stat['3★']} → 粉尘+{dust}"
    )
