# -*- coding: utf-8 -*-
from nonebot import on_keyword
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models import get_player, score_of_slots, slots_to_rank
from ..utils import ids_of

profile_m = on_keyword({"面板", "状态", "信息"})


@profile_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    slots = p["weapon"]["slots"]
    await profile_m.finish(
        f"【面板】{p['name']} Lv.{p['level']}\n"
        f"武器：{p['weapon']['name']}（{slots_to_rank(slots)}｜评分{score_of_slots(slots)}）\n"
        f"加点：力{p['points']['str']} 防{p['points']['def']} 血{p['points']['hp']} 敏{p['points']['agi']} 暴{p['points']['crit']}\n"
        f"未分配点：{p['unspent']}\n"
        f"粉尘：{p['dust']} 钻石：{p['diamond']} 探索券：{p['ticket']} 女神之泪：{p['tear']}\n"
        f"今日：远征{p['counters']['free_explore_used']}/2 出刀{p['counters']['boss_hits']}/3 签到：{'已' if p['counters']['signed'] else '未'}"
    )
