import random
import re
from typing import Dict

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_fullmatch, on_regex

from mybot.plugins.rpg.handlers.wild import format_chinese
from mybot.plugins.rpg.models import get_player, put_player, equip_skill, get_skill, level_up_skill, forget_skill
from mybot.plugins.rpg.util.config_loader import ConfigLoader
from mybot.plugins.rpg.utils import ids_of

_skill_info = on_fullmatch("技能")

@_skill_info.handle()
async def _():
    config_loader = ConfigLoader()
    skill_dict = config_loader.get_all_skills()
    res = "目前已实装的技能如下：\n"
    for _, skill_data in skill_dict.items():
        res += skill_data["description"] + "\n"
    res += f"\n【指令】输入'查看技能' 可以查看目前拥有的技能"
    await _skill_info.finish(res)


_get_skill = on_fullmatch(("抽技能","抽取技能"))

@_get_skill.handle()
async def _(event: MessageEvent):
    config_loader = ConfigLoader()
    skills_map = config_loader.get_skills_map(True)
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    if p.dust < 2000:
        await _get_skill.finish(f"粉尘不足，当前{p.dust}")
    p.dust -= 2000

    # 增加随机事件
    event_chance = random.randint(1, 100)
    print(event_chance)

    # 15%几率触发特殊事件
    if event_chance <= 15:
        special_events = [
            {
                "text": "抽取过程中发生了意外！技能书突然自燃了，但幸运的是，灰烬中闪耀着几颗钻石...",
                "compensation": "作为补偿，你获得了{diamond}💎！"
            },
            {
                "text": "一只神秘的小精灵飞过，带走了你的技能书！不过它留下了一些闪亮的钻石作为交换...",
                "compensation": "小精灵留下了{diamond}💎作为补偿！"
            },
            {
                "text": "技能书在你手中化作一道闪光消失了...但在光芒消散后，地上留下了几颗晶莹的钻石...",
                "compensation": "光芒消散后，你获得了{diamond}💎！"
            },
            {
                "text": "不知从哪里来的强风吹散了你的技能书！风停后，你发现地上散落着一些闪亮的钻石...",
                "compensation": "你在风中捡到了{diamond}💎！"
            },
            {
                "text": "wym偷走了你的技能书！不过这个调皮的小家伙还算有良心，留下了一些钻石作为补偿...",
                "compensation": "wym留下了{diamond}💎作为补偿！"
            }
        ]
        # 随机补偿50-150钻石
        diamond_compensation = random.randint(100, 2000)
        p.diamond += diamond_compensation  # 假设玩家对象有diamond属性

        # 随机选择一个事件
        selected_event = random.choice(special_events)

        # 构建完整消息
        event_message = selected_event["text"]
        compensation_message = selected_event["compensation"].format(diamond=diamond_compensation)
        full_message = event_message + '\n' + compensation_message
        print(full_message)

        put_player(p)
        await _get_skill.finish(full_message)

    # 获取玩家尚未拥有的技能
    available_skills = [skill_id for skill_id in skills_map.keys() if skill_id not in p.skills]

    if not available_skills or len(available_skills) == 0:
        await _get_skill.finish(f"没有新的技能啦！~")

    # 从技能映射中随机选择一个技能ID
    random_skill_id = random.choice(available_skills)

    res, ans = get_skill(p, random_skill_id, skills_map)
    put_player(p)
    await _get_skill.finish(ans)


# 存储每个用户的技能映射
user_skill_maps = {}
_show_skills = on_fullmatch("查看技能")

@_show_skills.handle()
async def _(event: MessageEvent):
    config_loader = ConfigLoader()
    skills_map = config_loader.get_skills_map(True)

    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    # 创建数字到技能的映射

    skill_map = {i: skill_name for i, skill_name in enumerate(p.skills.keys(), start=1)}

    # 格式化显示技能列表
    user_skill_maps[uid] = skill_map
    width = 15
    reply_msg = "【已拥有的技能】：\n"
    reply_msg += "编号："
    for num, skill in skill_map.items():
        reply_msg += f"{format_chinese(num, width)}"

    reply_msg += "\n名称："
    for num, skill in skill_map.items():
        reply_msg += f"{format_chinese(skills_map.get(skill).get("name"), width)}"
    reply_msg += "\n等级："
    for num, skill in skill_map.items():
        reply_msg += f"{format_chinese(p.skills.get(skill), width)}"

    equipped_skills_info = ""
    for i, skill in enumerate(p.equipped_skills):
        print(f"{i}. {skill}")
        equipped_skills_info += f"{i + 1}. {skills_map.get(skill).get('name')}\n"

    reply_msg += f"\n【已装配技能】：\n{equipped_skills_info}\n"
    reply_msg += f"\n【提示】技能需要装配才能生效，目前可以装配「{p.weapon.level}」个技能，目前可以记忆「{p.weapon.level+2}」个技能"
    reply_msg += f"\n【指令】输入'技能+数字'装配技能（例如：技能1）"
    reply_msg += f"\n【指令】输入'升级技能+数字'升级技能（例如：升级技能1）"
    reply_msg += f"\n【指令】输入'遗忘技能+数字'遗忘技能（例如：遗忘技能1）"

    await _show_skills.finish(reply_msg)

_level_up_skill = on_regex(r"^升级技能([1-5])$")
@_level_up_skill.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)

    if p.dust < 2000:
        await _get_skill.finish(f"粉尘不足，当前{p.dust}")
    p.dust -= 2000

    config_loader = ConfigLoader()
    skills_map = config_loader.get_skills_map(True)

    # 获取消息文本
    msg = event.get_plaintext()

    # 使用正则匹配获取选择
    match = re.match(r"^升级技能([1-9])$", msg)
    if not match:
        await _level_up_skill.finish("格式错误，请使用「升级技能1」、「升级技能2」或「升级技能3」")

    # 获取选择
    choice = int(match.group(1))  # 转换为0-based索引

    # 从映射中获取技能ID
    skill_id = user_skill_maps[uid].get(choice)

    if skill_id is None:
        await _level_up_skill.finish("无效的技能选择")
        return

    res, msg = level_up_skill(p, skill_id, skills_map)
    if not res:
        p.dust += 2000
    put_player(p)
    await _level_up_skill.finish(msg)

_forget_skill = on_regex(r"^遗忘技能([1-9])$")
@_forget_skill.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    config_loader = ConfigLoader()
    skills_map = config_loader.get_skills_map(True)

    # 获取消息文本
    msg = event.get_plaintext()

    # 使用正则匹配获取选择
    match = re.match(r"^遗忘技能([1-9])$", msg)
    if not match:
        await _forget_skill.finish("格式错误，请使用「遗忘技能1」、「遗忘技能2」或「遗忘技能3」")

    # 获取选择
    choice = int(match.group(1))  # 转换为0-based索引
    # 从映射中获取技能ID
    skill_id = user_skill_maps[uid].get(choice)

    if skill_id is None:
        await _forget_skill.finish("无效的技能选择")
        return

    res, msg = forget_skill(p, skill_id, skills_map)
    await _forget_skill.finish(msg)

_equip_skill = on_regex(r"^技能([1-9])$")
@_equip_skill.handle()
async def choose_expedition(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)

    config_loader = ConfigLoader()
    skills_map = config_loader.get_skills_map(True)

    # 获取消息文本
    msg = event.get_plaintext()

    # 使用正则匹配获取选择
    match = re.match(r"^技能([1-9])$", msg)
    if not match:
        await _equip_skill.finish("格式错误，请使用「技能1」、「技能2」或「技能3」")

    # 获取选择
    choice = int(match.group(1))  # 转换为0-based索引

    # 从映射中获取技能ID
    skill_id = user_skill_maps[uid].get(choice)

    if skill_id is None:
        await _equip_skill.finish("无效的技能选择")
        return

    res, msg = equip_skill(p, skill_id, skills_map)
    await _equip_skill.finish(msg)
