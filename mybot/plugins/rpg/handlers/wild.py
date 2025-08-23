# -*- coding: utf-8 -*-
import random
from nonebot import on_keyword
from nonebot.adapters.onebot.v11 import MessageEvent

from ..models.player import get_player
from ..utils import ids_of

wild_m = on_keyword({"远征", "打野"})


@wild_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    c = p["counters"]
    if c["free_explore_used"] < 2:
        c["free_explore_used"] += 1
    elif p["ticket"] > 0:
        p["ticket"] -= 1
    elif p["diamond"] >= 300:
        p["diamond"] -= 300
    else:
        await wild_m.finish("远征需要：每天2次免费 / 探索券 / 钻石300")
    dia = random.randint(30, 60)
    dus = random.randint(5, 15)
    p["diamond"] += dia
    p["dust"] += dus
    p.save()
    await wild_m.finish(
        f"远征完成：钻石+{dia} 粉尘+{dus}（今日免费{p['counters']['free_explore_used']}/2）"
    )
