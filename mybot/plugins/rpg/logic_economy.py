# -*- coding: utf-8 -*-
import pathlib
import random
from typing import LiteralString

import yaml


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
    return dust, "本次抽卡结果：\n"+"\n".join(character_names)