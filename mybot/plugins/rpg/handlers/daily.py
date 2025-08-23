# -*- coding: utf-8 -*-
from nonebot import on_keyword
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models import get_player, put_player
from ..logic_economy import gacha10_to_dust
from ..utils import ids_of

daily_m = on_keyword({"签到"})


@daily_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    if p["counters"]["signed"]:
        await daily_m.finish("今天已签到过了")
    dust, stat = gacha10_to_dust()
    p["dust"] += dust
    p["counters"]["signed"] = True
    put_player(p)
    await daily_m.finish(
        f"签到成功：5★{stat['5★']} 4★{stat['4★']} 3★{stat['3★']} → 粉尘+{dust}"
    )
