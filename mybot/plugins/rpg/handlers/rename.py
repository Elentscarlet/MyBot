# -*- coding: utf-8 -*-
import re
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models import get_player, put_player
from ..utils import ids_of, text_of

rename_m = on_regex(r"^(起名|改名)\s*(.+)$")


@rename_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    m = re.match(r"^(起名|改名)\s*(.+)$", text_of(event))
    new_name = m.group(2).strip()[:20]
    p.weapon.name = new_name
    put_player(p)
    await rename_m.finish(f"已改名：{new_name}")
