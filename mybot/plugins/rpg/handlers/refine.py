# -*- coding: utf-8 -*-
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_fullmatch

from ..models import get_player, put_player
from ..utils import ids_of

refine_m = on_fullmatch("精炼")


@refine_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)

    _,msg = p.weapon.refine(p)
    put_player(p)
    await refine_m.finish(msg)


refine_10 = on_fullmatch(("精炼十连", "精炼10"))


@refine_10.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    msg = ""
    for i in range(10):
        success, res = p.weapon.refine(p)
        print(success, res)
        if success:
            msg += res + '\n'
        else:
            msg += res + '\n'
            break
    print(msg)
    put_player(p)
    await refine_m.finish(msg)
