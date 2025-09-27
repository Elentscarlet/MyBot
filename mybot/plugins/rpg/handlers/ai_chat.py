# -*- coding: utf-8 -*-
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_message
from nonebot.rule import to_me

from mybot.plugins.rpg.engine.ai_chat import get_chat_response

chat_m = on_message(rule=to_me(), priority=10, block=True)


@chat_m.handle()
async def handle_chat_message(event: MessageEvent):
    # 获取原始的、未经处理的消息内容
    raw_msg = event.get_plaintext().strip()
    response = get_chat_response(raw_msg)
    print(response)
    await chat_m.send(response)
