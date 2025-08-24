# -*- coding: utf-8 -*-
import pathlib
import random
import time
from collections import defaultdict
from typing import LiteralString

import yaml

from mybot.plugins.rpg.models import Player, put_player


# 抽卡 ------------------------------------------------------------------
def gacha10_to_dust() -> tuple[int, LiteralString]:
    root = pathlib.Path(__file__).resolve().parent  # .../rpg
    character_path = root / "data" / "character.yaml"

    stars = []
    for _ in range(10):
        r = random.random()
        if r < 0.03:
            stars.append(5)
        elif r < 0.23:
            stars.append(4)
        else:
            stars.append(3)
    data = yaml.safe_load(character_path.read_text(encoding="utf-8")) or []
    # 构建星级到角色列表的映射
    star_to_characters = {}
    for item in data['characterList']:
        star_to_characters[item['star']] = item['character']

    # 获取每个星级对应的随机角色名称
    character_names = []
    for star in stars:
        characters = star_to_characters.get(star, [])
        if characters:
            character_name = random.choice(characters)
            character_names.append(f"{star}★{character_name}")
        else:
            character_names.append(f"{star}★未知角色")

    dust = sum(600 if s == 5 else 120 if s == 4 else 30 for s in stars)
    return dust, "本次抽卡结果：\n" + "\n".join(character_names)


# 钓鱼 ------------------------------------------------------------------
# 存储每个群组的钓鱼计数器和最后重置时间
fishing_counters = defaultdict(int)
last_reset_times = defaultdict(float)


def get_counter(gid):
    current_time = time.time()
    last_reset = last_reset_times[gid]

    # 检查是否需要重置（每小时重置）
    if current_time - last_reset >= 7200:  # 3600秒 = 1小时
        fishing_counters[gid] = 0
        last_reset_times[gid] = current_time

    return fishing_counters[gid]


def increment_counter(gid):
    """增加计数器值"""
    fishing_counters[gid] += 1
    return fishing_counters[gid]


def get_pool_prob(count, size):
    return 1 - (count / size) ** 3


def get_fish(gid):
    root = pathlib.Path(__file__).resolve().parent  # .../rpg
    fish_path = root / "data" / "fish.yaml"
    data = yaml.safe_load(fish_path.read_text(encoding="utf-8")) or {}

    count = get_counter(gid)
    pool_size = data.get('pool_size', 10)

    # 计算概率
    probability = data.get('prob', 0) * get_pool_prob(count, pool_size)
    r = random.random()

    # 判断是否成功钓到鱼
    if r < probability:
        # 钓到鱼的情况：计数器增加，剩余鱼数减少
        increment_counter(gid)
        remaining_fish = pool_size - (count + 1)  # 钓到鱼后剩余数量

        pool_msg = f"池塘里还剩下[{remaining_fish}]条鱼。"
        if remaining_fish == 0:
            pool_msg += "这里已经没有鱼了，去别处试一试吧~"
        elif probability < 0.2:
            pool_msg += "这里的鱼已经很警惕了，去别处试一试吧~"

        # 随机选择一条鱼
        if data.get('list'):
            return [random.choice(data['list']), pool_msg]
        raise Exception("鱼类信息获取错误")
    else:
        # 没钓到鱼的情况：计数器不变，剩余鱼数不变
        remaining_fish = pool_size - count  # 剩余数量不变

        pool_msg = f"池塘里还剩下[{remaining_fish}]条鱼。"
        if remaining_fish == 0:
            pool_msg += "这里已经没有鱼了，去别处试一试吧~"
        elif probability < 0.2:
            pool_msg += "这里的鱼已经很警惕了，去别处试一试吧~"

        return [None, pool_msg]
