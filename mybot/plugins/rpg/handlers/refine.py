# -*- coding: utf-8 -*-
import re
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models import get_player, put_player, refine_cost, slots_to_rank, score_of_slots
from ..utils import ids_of, text_of

refine_m = on_regex(r"^精炼\s*([123])$")


@refine_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    idx = int(re.match(r"^精炼\s*([123])$", text_of(event)).group(1))
    cur = p["weapon"]["slots"][idx - 1]
    if cur >= 4:
        await refine_m.finish("该槽位已是S")
    nxt = cur + 1
    cost = refine_cost(nxt)
    if p["dust"] < cost:
        await refine_m.finish(f"粉尘不足，需要{cost}")
    p["dust"] -= cost
    p["weapon"]["slots"][idx - 1] = nxt
    put_player(p)
    slots = p["weapon"]["slots"]
    await refine_m.finish(
        f"精炼成功：段位{slots_to_rank(slots)}｜评分{score_of_slots(slots)}｜粉尘{p['dust']}"
    )
