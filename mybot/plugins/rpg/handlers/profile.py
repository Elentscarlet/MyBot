# -*- coding: utf-8 -*-
from nonebot.adapters.onebot.v11 import MessageEvent, Message
from nonebot.internal.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.plugin.on import on_fullmatch, on_regex

from ..models import get_player
from ..utils import ids_of, first_at

# 查看他人面板
profile_cmd = on_regex(r"^(面板)|(面板)$")


@profile_cmd.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)

    target_uid = first_at(event)
    if not target_uid:
        msg = p.get_profile()
        msg += "\n\n 提示：如果要查看他人数据：面板 @某人"
        await profile_cmd.finish(msg)

    p = get_player(target_uid, gid, "")  # 查看目标用户的面板

    await profile_cmd.finish(p.get_profile())
