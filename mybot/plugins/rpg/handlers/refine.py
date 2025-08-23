# -*- coding: utf-8 -*-
import re
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models import get_player, put_player
from ..utils import ids_of, text_of

refine_m = on_regex(r"^精炼\s*([123])$")


@refine_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    idx = int(re.match(r"^精炼\s*([123])$", text_of(event)).group(1))

    # 用“钱包”方式传递粉尘（也可以把 player 直接传给 Weapon.refine）
    wallet = {"dust": p.dust}
    msg = p.weapon.refine(idx, wallet)
    p.dust = wallet["dust"]
    put_player(p)
    await refine_m.finish(msg)
