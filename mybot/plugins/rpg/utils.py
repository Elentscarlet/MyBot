# -*- coding: utf-8 -*-
from typing import Optional
from nonebot.adapters.onebot.v11 import MessageEvent


def text_of(event: MessageEvent) -> str:
    return str(event.get_message()).strip()


def ids_of(event: MessageEvent):
    uid = str(event.user_id)
    gid = str(getattr(event, "group_id", 0))
    try:
        name = event.sender.card or event.sender.nickname
    except Exception:
        name = uid
    return uid, gid, name


def first_at(event: MessageEvent) -> Optional[str]:
    for seg in event.message:
        if seg.type == "at" and "qq" in seg.data:
            return str(seg.data["qq"])
    return None
