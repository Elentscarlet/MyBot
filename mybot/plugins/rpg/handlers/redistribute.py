from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models import get_player, put_player, Points
from ..utils import ids_of

# 匹配“加点99080”或“加点 99080”等格式
redistribute_m = on_regex(r"^加点\s*([0-9]{5})")


@redistribute_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    re_match = event.get_plaintext().strip()
    import re

    m = re.match(r"^加点\s*([0-9]{5})", re_match)
    if not m:
        await redistribute_m.finish("格式错误，请输入：加点99080 或 加点 99080")
    digits = m.group(1)
    points = [int(x) for x in digits]
    total = sum(points)
    if total > 26:
        for i in range(4, -1, -1):
            if total <= 26:
                break
            remove = min(points[i], total - 26)
            points[i] -= remove
            total -= remove
    p.points = Points(
        str=points[0], def_=points[1], hp=points[2], agi=points[3], crit=points[4]
    )
    put_player(p)
    await redistribute_m.finish(
        f"{p.name} 的点数已分配为：力量{points[0]}、防御{points[1]}、体力{points[2]}、敏捷{points[3]}、暴击{points[4]}（共{sum(points)}点）"
    )
