# -*- coding: utf-8 -*-
import random
import re

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_fullmatch, on_startswith

from ..models import get_player, put_player
from ..utils import ids_of

# 新增精炼数字指令
refine_num = on_startswith("精炼")


@refine_num.handle()
async def _(event: MessageEvent):
    # 提取消息中的数字
    message = event.get_plaintext().strip()
    match = re.search(r"精炼\s*(\d+)", message)

    if not match:
        await refine_num.finish("指令格式错误，请使用「精炼+数字」，例如：精炼100")

    num = 0
    try:
        num = int(match.group(1))
        if num <= 0:
            await refine_num.finish("精炼次数必须大于0")
        if num > 2000:  # 设置上限防止滥用
            await refine_num.finish("单次精炼次数不能超过2000次")
    except ValueError:
        await refine_num.finish("指令格式错误，请使用「精炼+数字」，例如：精炼100")

    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)

    msg = ""
    count = 0
    total_cost = 0
    completed = False

    for i in range(num):
        success, res, cost = p.weapon.refine(p)
        total_cost += cost
        if cost != 0:
            count += 1
        if success:
            msg += res
            completed = True
            break  # 成功则立即结束
    msg += f"共执行{count}次精炼总计消耗{total_cost}✨"
    taunts = [
        f"\n哼哼~{name}真是个大笨蛋呢！浪费了这么多资源还是一事无成，真是让人笑掉大牙啦！♪",
        f"\n诶嘿嘿~{name}的手气真是差到极点呢！连一次成功都没有，要不要我教你正确的精炼方法呀？虽然教了你也学不会就是了~",
        f"\n噗哈哈哈！{name}真是个小倒霉蛋呢！{num}次全败，这种运气还是去买彩票吧~说不定能中个安慰奖呢！",
        f"\n哇哦~{name}的失败记录又刷新了呢！这么多次都成功不了，是不是该考虑换个职业呀？比如说...去当个吉祥物？",
        f"\n啧啧啧~{name}的精炼技术真是让人大开眼界呢！连最基本的成功都做不到，要不要跪下来求求姐姐帮忙呀？",
        f"\n啊啦啊啦~{name}又在这里浪费资源了呢！这么多资源给我多好，至少不会全部打水漂哦~",
        f"\n嘻嘻~{name}的运气真是差得可爱呢！要不要姐姐给你一个幸运之吻呀？虽然吻了也不会有什么改变就是了~",
        f"\n哼哼~{name}的精炼记录简直可以载入史册了呢！作为反面教材的那种~真是让人忍不住想要嘲笑你呢！"
    ]
    no_dust = [
        f"\n哼~连粉尘都没有就想精炼？你这笨蛋是在做什么白日梦呢！♪",
        f"\n诶~没有粉尘还在这里装模作样地精炼？真是让人笑掉大牙啦！",
        f"\n~没有粉尘的精炼就像没有鱼饵的钓鱼，你在钓空气吗？",
        f"\n叮~检测到粉尘库存空空如也！精炼指令暂时无法执行哦！",
        f"\n嗯？你根本就没有粉尘精炼，不要在这里乱打指令了！"
    ]
    if not completed:
        # 循环结束但未成功（所有尝试都失败）
        msg += f"\n所有精炼均失败！"
        if count >= 50:
            msg += random.choice(taunts)
        if count == 0:
            msg += random.choice(no_dust)
        if count < num:
            msg += f"\n你的粉尘✨好像花完了，快去看看吧"

    put_player(p)
    await refine_num.finish(msg)
