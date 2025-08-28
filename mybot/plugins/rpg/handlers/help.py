# -*- coding: utf-8 -*-
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_fullmatch

from mybot.plugins.rpg.models import get_player, put_player
from mybot.plugins.rpg.utils import ids_of

help_m = on_fullmatch(("帮助", "菜单", "指令", "help"))

@help_m.handle()
async def _():
    await help_m.finish(
        "【RPG帮助】\n"
        "起名 <名字>：设置武器名\n"
        "面板 <@对应玩家>：查看角色面板，不@则只查看自己\n"
        "列表：本群玩家\n"
        "签到：每日免费十连\n"
        "十连/抽卡：花钻石十连（产粉尘）\n"
        "钓鱼：花费少量钻石进行钓鱼活动，可以触发随机事件\n"
        "抢夺 <@其他玩家>：抢夺其他玩家的钻石\n"
        "精炼<数字>：精炼武器，当新评分大于旧评分时，自动替换三槽评级\n"
        "远征/打野：获得钻石+粉尘（每天2次免费）\n"
        "对战 <@对手>：群内自动对战\n"
        "BOSS：查看世界BOSS｜出刀：攻击BOSS（每天3次）\n"
        "加点:力量 防御 体力 敏捷 暴击：如 加点99080（总和不超过26，超出部分自动截断）\n"
    )

battle_report_cmd_0 = on_fullmatch("完整战报")
@battle_report_cmd_0.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    p.config.battle_report_model = 0
    put_player(p)
    await battle_report_cmd_0.finish(f"{p.name}已调整为完整战报模式：显示所有对战日志")

battle_report_cmd_1 = on_fullmatch("精简战报")
@battle_report_cmd_1.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    p.config.battle_report_model = 1
    put_player(p)
    await battle_report_cmd_1.finish(f"{p.name}已调整为精简战报模式：只显示每回合主要动作")

battle_report_cmd_2 = on_fullmatch("无战报")
@battle_report_cmd_2.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    p.config.battle_report_model = 2
    put_player(p)
    await battle_report_cmd_2.finish(f"{p.name}已调整为无战报模式：只显示结果")