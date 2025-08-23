# -*- coding: utf-8 -*-
from nonebot import on_keyword
from nonebot.adapters.onebot.v11 import MessageEvent
from ..storage import load_players

list_m = on_keyword({"列表", "成员", "玩家"})


@list_m.handle()
async def _(event: MessageEvent):
    gid = str(getattr(event, "group_id", 0))
    players = load_players()
    names = [p["name"] for p in players.values() if p["gid"] == gid]
    await list_m.finish("本群玩家：" + ("、".join(names) if names else "暂无"))
