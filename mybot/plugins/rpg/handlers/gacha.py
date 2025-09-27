# -*- coding: utf-8 -*-
import re

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_fullmatch, on_startswith

from ..logic_economy import gacha10_to_dust, gacha_num_to_dust
from ..models import get_player, put_player
from ..utils import ids_of

gacha_m = on_fullmatch(("十连", "抽卡"), priority=10,block=True)

@gacha_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    if p.diamond < 1500:
        await gacha_m.finish(f"钻石不足，当前{p.diamond}")
    p.diamond -= 1500
    dust, stat = gacha10_to_dust()
    p.dust += dust
    put_player(p)
    await gacha_m.finish(
        f"十连完成：{stat}\n总计获得粉尘：{dust}✨,剩余钻石：{p.diamond}"
    )


gacha_m_100 = on_startswith("抽卡", priority=9,block=True)

@gacha_m_100.handle()
async def num_gacha(event: MessageEvent):
    # 提取消息中的数字
    message = event.get_plaintext().strip()
    match = re.search(r"抽卡\s*(\d+)", message)

    if not match:
        await gacha_m_100.finish("指令格式错误，请使用「抽卡+数字」，例如：抽卡100")

    num = 0
    try:
        num = int(match.group(1))
        if num < 10:
            await gacha_m_100.finish("抽卡次数必须大于10")
        if num > 200:  # 设置上限防止滥用
            await gacha_m_100.finish("抽卡次数不能超过200次")
    except ValueError:
        await gacha_m_100.finish("指令格式错误，请使用「抽卡+数字」，例如：抽卡100")

    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    if p.diamond < 150 * num:
        await gacha_m_100.finish(f"钻石不足，当前{p.diamond}💎，需要{150 * num}💎")
    p.diamond -= 150 * num
    dust, stat = gacha_num_to_dust(num)
    p.dust += dust
    put_player(p)
    await gacha_m_100.finish(
        f"抽卡完成：{stat}\n总计获得粉尘：{dust}✨，剩余钻石：{p.diamond}💎"
    )
