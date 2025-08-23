from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from ..models import get_player, put_player, Points
from ..utils import ids_of

redistribute_m = on_command("重置点数")


@redistribute_m.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    p.points = Points.default()
    put_player(p)
    await redistribute_m.finish(
        f"{p.name} 的点数已重置为：力量8、防御6、体力6、敏捷6、暴击0（共26点）\n如需自定义分配，请联系管理员或等待后续功能。"
    )
