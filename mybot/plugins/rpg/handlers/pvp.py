# -*- coding: utf-8 -*-
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, Bot

from ..models import get_player
from ..logic_battle import simulate_pvp_with_skills
from ..utils import ids_of, first_at

# 优先使用“配表技能”的装备函数；若不存在则回落到内置 equip_skills_for_player
try:
    from ..skill_config import equip_skills_for_player_from_cfg as equip_skills_for_player  # type: ignore
except Exception:
    from ..logic_skill import equip_skills_for_player  # 旧版内置

pvp_m = on_regex(r"^(对战|pk)")


@pvp_m.handle()
async def _(event: MessageEvent, bot: Bot):
    gid = str(getattr(event, "group_id", 0))
    uid, gid, name = ids_of(event)

    target = first_at(event)
    if not target or target == uid:
        await pvp_m.finish("用法：对战 @某人")

    # 加载双方玩家（OOP）
    a = get_player(uid, gid, name)
    info = await bot.get_group_member_info(group_id=int(gid), user_id=int(target))
    b = get_player(target, gid, info.get("card") or info.get("nickname") or target)

    # 使用新版PVP接口
    result, logs = simulate_pvp_with_skills(a, b)
    await pvp_m.finish("\n".join(logs))
