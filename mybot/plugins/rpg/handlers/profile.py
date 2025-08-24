# -*- coding: utf-8 -*-
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_fullmatch

from ..models import get_player
from ..utils import ids_of

profile_m = on_fullmatch(("面板", "状态", "信息"))

@profile_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)

    await profile_m.finish(
        p.get_profile()
    )
