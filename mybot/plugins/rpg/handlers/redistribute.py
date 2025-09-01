import re

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
        await redistribute_m.finish("格式错误，请输入：加点99040 或 加点 99040")
    digits = m.group(1)
    points = [int(x) for x in digits]
    total = sum(points)
    if total > 23:
        for i in range(4, -1, -1):
            if total <= 23:
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


cmd_distribute = on_regex(r"^升级", priority=10)


@cmd_distribute.handle()
async def _(event: MessageEvent):
    print(event.message)
    # 获取原始消息文本
    msg_text = event.get_plaintext().strip()

    # 使用正则匹配
    match = re.match(r"^升级([\u4e00-\u9fa5]{2})$", msg_text)
    if not match:
        await cmd_distribute.finish("命令格式错误！请使用：升级XX（力量, 防御, 体力, 敏捷, 暴击）")

    # 提取属性参数
    attribute = match.group(1)

    # 定义可用选项
    allowed_options = ["力量", "防御", "体力", "敏捷", "暴击"]

    if attribute not in allowed_options:
        await cmd_distribute.finish(f"无效的属性！可用选项：{'、'.join(allowed_options)}")

    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    if p.tear < 1:
        await cmd_distribute.finish(f"女神之泪不足,无法提升属性")
    # 处理有效的属性升级
    p.extra_distribute(attribute)

    await cmd_distribute.finish(f"升级完成！当前属性:\n" + p.get_point_detail())
