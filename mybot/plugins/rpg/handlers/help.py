# -*- coding: utf-8 -*-
from nonebot import on_keyword

help_m = on_keyword({"帮助", "菜单", "指令", "help"})


@help_m.handle()
async def _():
    await help_m.finish(
        "【RPG帮助】\n"
        "起名 <名字>：设置武器名\n"
        "面板：查看角色｜列表：本群玩家\n"
        "签到：每日免费十连\n"
        "十连/抽卡：花钻石十连（产粉尘）\n"
        "精炼1/2/3：精炼对应槽位\n"
        "远征/打野：获得钻石+粉尘（每天2次免费）\n"
        "对战 @对手：群内自动对战\n"
        "BOSS：查看世界BOSS｜出刀：攻击BOSS（每天3次）\n"
        "加点 力量 防御 体力 敏捷 暴击：如 加点 9 9 0 8 0（总和不超过26，超出部分自动截断）\n"
    )
