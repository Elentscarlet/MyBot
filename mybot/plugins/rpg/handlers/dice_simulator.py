# -*- coding: utf-8 -*-
import re

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_keyword

from mybot.plugins.rpg.engine.dice import DiceSimulator

# 使用命令方式匹配，更灵活
dice_cal = on_keyword({"概率计算", "骰子"}, priority=1, block=True)

@dice_cal.handle()
async def _(event: MessageEvent):
    # 获取原始消息文本
    msg = event.get_plaintext()

    # 使用正则表达式匹配三个数字
    match = re.search(r'(\d+)\s+(\d+)\s+(\d+)', msg)

    if not match:
        # 如果没有匹配到三个数字，发送使用说明
        await dice_cal.finish("用法: 骰子 n m x (三个数字，分别为骰子数，抽卡数，目标检定值)\n例如: 骰子 10 5 3")

    try:
        # 提取并转换参数
        n = int(match.group(1))
        m = int(match.group(2))
        x = int(match.group(3))

        # 这里可以添加您的概率计算逻辑
        simulator = DiceSimulator()
        msg = simulator.run_simulation(n, m, x)

        # 暂时先返回接收到的参数
        await dice_cal.finish(msg)

    except ValueError:
        await dice_cal.finish("参数必须是整数")
