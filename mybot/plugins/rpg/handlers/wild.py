# -*- coding: utf-8 -*-
import pathlib
import random
import re
from typing import Dict

import yaml
from nonebot import on_fullmatch
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent

from mybot.plugins.rpg.logic_battle import simulate_duel_with_skills
from mybot.plugins.rpg.models import get_player, put_player
from mybot.plugins.rpg.utils import ids_of

wildStart_m = on_fullmatch(("发起远征", "远征"))
wildChoose_m = on_regex(r"^远征([1-3])$")
wildend_m = on_fullmatch("结束远征")

# 简单内存存储（生产建议用redis等持久化）
expedition_state = {}


# === 工具：加载怪物定义 ===
def _load_monsters() -> Dict:
    path = pathlib.Path(__file__).resolve().parent.parent / "battle" / "monsters.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return data


def get_expedition_key(event: MessageEvent):
    return f"{event.user_id}_{getattr(event, 'group_id', 0)}"


# 适配QQ长度，一个汉字大概3.5，一个数字大概2
def format_chinese(text, width):
    # 确保text是字符串类型
    if not isinstance(text, str):
        text = str(text)
    # 计算中文字符和数字的数量（每个占2个英文字符宽度）
    chinese_chars_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    digit_count = sum(1 for c in text if c.isdigit())
    # 计算其他字符数量（英文字母、标点符号等）
    other_count = len(text) - digit_count - chinese_chars_count
    # 计算总占位宽度（宽字符占2位，其他字符占1位）
    total_width = int(chinese_chars_count * 3.5) + digit_count * 2 + other_count

    if total_width >= width:
        return text

    # 添加空格填充
    spaces = ' ' * (width - total_width)
    return text + spaces


def build_monster_msg(selected_monsters, width=15):
    reply_msg = "请选择你要远征的目标：\n\n"
    reply_msg += "编号："
    for i, monster in enumerate(selected_monsters, 1):
        reply_msg += f"{format_chinese(i, width)}"
    reply_msg += '\n'
    reply_msg += "名称："
    for i, monster in enumerate(selected_monsters, 1):
        reply_msg += f"{format_chinese(monster['name'], width)}"
    reply_msg += '\n'
    reply_msg += "血量："
    for i, monster in enumerate(selected_monsters, 1):
        reply_msg += f"{format_chinese(monster['MAX_HP'], width)}"
    reply_msg += '\n'
    reply_msg += "攻击："
    for i, monster in enumerate(selected_monsters, 1):
        reply_msg += f"{format_chinese(monster['ATK'], width)}"
    reply_msg += '\n'
    reply_msg += "防御："
    for i, monster in enumerate(selected_monsters, 1):
        reply_msg += f"{format_chinese(monster['DEF'], width)}"
    reply_msg += '\n'
    reply_msg += "敏捷："
    for i, monster in enumerate(selected_monsters, 1):
        reply_msg += f"{format_chinese(monster['AGI'], width)}"
    reply_msg += '\n'
    reply_msg += "暴击："
    for i, monster in enumerate(selected_monsters, 1):
        reply_msg += f"{format_chinese(int(monster['CRIT'] * 100), width)}"
    reply_msg += '\n'
    return reply_msg


@wildStart_m.handle()
async def start_expedition(event: MessageEvent):
    # 加载玩家数据
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)

    reply_msg = ""
    if p.counters.free_explore_used < 2:
        p.counters.free_explore_used += 1
    elif p.diamond >= 500:
        p.diamond -= 500
        reply_msg += "本日免费远征次数已耗尽，花费500钻开始远征"
    else:
        reply_msg = "本日免费远征次数已耗尽，钻石不足无法开始远征"
        await wildStart_m.finish(reply_msg)
        return

    put_player(p)
    # 加载怪物数据
    monsters_data = _load_monsters()

    # 首先筛选出所有等级为1的怪物
    selected_monsters = [monster for monster in monsters_data if monster['level'] == 1 and monster['tag'] == 'monster']
    # 随机选择3个怪物
    selected_monsters = random.sample(selected_monsters, 3)

    # 存储选择状态
    key = get_expedition_key(event)
    expedition_state[key] = {
        "monsters": selected_monsters,
        "diamond": 0,
        "round": 1
    }

    # 构建回复消息 - 表格形式展示怪物信息
    reply_msg = build_monster_msg(selected_monsters)

    reply_msg += "\n回复「远征1」、「远征2」或「远征3」来选择目标"

    await wildStart_m.finish(reply_msg)


@wildChoose_m.handle()
async def choose_expedition(event: MessageEvent, match=wildChoose_m):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)

    key = get_expedition_key(event)

    # 检查是否有进行中的远征
    if key not in expedition_state:
        await wildChoose_m.finish("你还没有发起远征，请先发送「发起远征」")

    # 获取消息文本
    msg = event.get_plaintext()

    # 使用正则匹配获取选择
    match = re.match(r"^远征([1-3])$", msg)
    if not match:
        await wildChoose_m.finish("格式错误，请使用「远征1」、「远征2」或「远征3」")

    # 获取选择
    choice = int(match.group(1)) - 1  # 转换为0-based索引

    # 获取对应的怪物
    state = expedition_state[key]
    if choice < 0 or choice >= len(state["monsters"]):
        await wildChoose_m.finish("选择无效，请选择1-3之间的数字")

    selected_monster = state["monsters"][choice]
    round = state["round"]

    # 直接用 boss 名称作为怪物ID，要求 monsters.yaml 里有同名boss定义
    winner, logs, _ = simulate_duel_with_skills(p, selected_monster['name'], max_turns=10)
    result_msg = "\n".join(logs)

    if winner == p.name:
        round += 1
        # 计算奖励
        reward = calculate_reward(selected_monster)
        result_msg += f" 你击败了{selected_monster['name']}！\n"

        monsters_data = _load_monsters()
        # 首先筛选出所有等级为1的怪物

        round_threshold = int(round / 3)
        min_level = min(5, round_threshold - 1)
        max_level = 1 + round_threshold

        selected_monsters = [
            monster for monster in monsters_data
            if min_level <= monster['level'] <= max_level
               and monster['tag'] == 'monster'
        ]

        # 随机选择3个怪物
        selected_monsters = random.sample(selected_monsters, 3)
        # 存储选择状态
        key = get_expedition_key(event)

        total_reward = state["diamond"] + reward
        expedition_state[key] = {
            "monsters": selected_monsters,
            "diamond": total_reward,
            "round": round
        }

        # 构建回复消息
        result_msg += f"累积获得[{total_reward}]💎，请选择下一个的目标或[结束远征]：\n"
        result_msg += build_monster_msg(selected_monsters)
        result_msg += "\n回复「远征1」、「远征2」或「远征3」来选择目标"

    else:
        result_msg += f"远征失败！{selected_monster['name']}太强大了，你被迫撤退。"
        del expedition_state[key]

    # 清除状态

    await wildChoose_m.finish(result_msg)


@wildend_m.handle()
async def end_wild(event: MessageEvent):
    key = get_expedition_key(event)
    state = expedition_state[key]
    reward = state["diamond"]

    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)

    p.diamond += reward
    put_player(p)

    del expedition_state[key]
    await wildend_m.finish(f"结束远征，获得{reward}钻石")


def calculate_reward(monster: Dict) -> int:
    """根据怪物等级计算奖励"""
    level = monster["level"]
    base_exp = 100 * (1.8 ** (level - 1))
    # 添加 ±10% 的随机浮动
    random_factor = random.uniform(0.9, 1.1)  # 90% 到 110% 之间的随机数
    final_exp = base_exp * random_factor

    return int(final_exp)
