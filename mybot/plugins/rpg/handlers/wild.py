# -*- coding: utf-8 -*-
import random
from nonebot import on_fullmatch
from nonebot import get_driver
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models import get_player, put_player
from ..utils import ids_of


wildStart_m = on_fullmatch({"发起远征"})
wildChoose_m = on_regex(r"^远征([1-3])$")


# 简单内存存储（生产建议用redis等持久化）
expedition_state = {}


def get_expedition_key(event: MessageEvent):
    return f"{event.user_id}_{getattr(event, 'group_id', 0)}"


@wildStart_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    c = p.counters

    if c.free_explore_used < 2:
        c.free_explore_used += 1
    elif p.diamond >= 300:
        p.diamond -= 300
    else:
        await wildStart_m.finish("远征需要：每天2次免费 / 钻石300")

    dia = random.randint(30, 60)
    dus = random.randint(5, 15)
    p.diamond += dia
    p.dust += dus
    put_player(p)
    await wildStart_m.finish(
        f"远征完成：钻石+{dia} 粉尘+{dus}（今日免费{p.counters.free_explore_used}/2）"
    )


@wildChoose_m.handle()
async def _(event: MessageEvent):
    key = get_expedition_key(event)
    state = expedition_state.get(key)
    if not state:
        await wildChoose_m.finish("请先“发起远征”！")
    idx = int(event.get_plaintext()[-1]) - 1
    monster = state["monsters"][idx]
    # 这里写你的战斗模拟函数，返回日志和胜负
    log, win = simulate_expedition_battle(get_player(*ids_of(event)), monster)
    msg = f"【战斗日志】\n{log}\n"
    if win:
        dia, dus = monster["reward"]
        state["reward"] += dia
        state["dust"] += dus
        state["step"] += 1
        # 生成更强怪物
        monsters = [
            {
                "name": "史莱姆王",
                "level": "简单",
                "ATK": 8 + state["step"] * 2,
                "DEF": 2 + state["step"],
                "HP": 40 + state["step"] * 10,
                "reward": (20 + state["step"] * 5, 3 + state["step"]),
            },
            {
                "name": "兽人",
                "level": "中等",
                "ATK": 15 + state["step"] * 2,
                "DEF": 5 + state["step"],
                "HP": 80 + state["step"] * 10,
                "reward": (40 + state["step"] * 5, 7 + state["step"]),
            },
            {
                "name": "魔像王",
                "level": "困难",
                "ATK": 25 + state["step"] * 2,
                "DEF": 10 + state["step"],
                "HP": 150 + state["step"] * 10,
                "reward": (80 + state["step"] * 5, 15 + state["step"]),
            },
        ]
        state["monsters"] = monsters
        msg += f"胜利！累计奖励：钻石{state['reward']} 粉尘{state['dust']}\n"
        msg += "请选择下一波怪物：\n"
        for i, m in enumerate(monsters, 1):
            msg += f"{i}. {m['name']}（{m['level']}）ATK:{m['ATK']} DEF:{m['DEF']} HP:{m['HP']}\n"
        msg += "请输入“远征1”“远征2”“远征3”选择怪物"
        await wildChoose_m.finish(msg)
    else:
        # 结算奖励
        p = get_player(*ids_of(event))
        p.diamond += state["reward"]
        p.dust += state["dust"]
        put_player(p)
        expedition_state.pop(key, None)
        msg += (
            f"挑战失败，远征结束！累计奖励：钻石{state['reward']} 粉尘{state['dust']}"
        )
        await wildChoose_m.finish(msg)
