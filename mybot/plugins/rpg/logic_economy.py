# -*- coding: utf-8 -*-
import random
from typing import Tuple, Dict


def gacha10_to_dust() -> Tuple[int, Dict[str, int]]:
    stars = []
    for _ in range(10):
        r = random.random()
        if r < 0.03:
            stars.append(5)
        elif r < 0.23:
            stars.append(4)
        else:
            stars.append(3)
    dust = sum(600 if s == 5 else 120 if s == 4 else 30 for s in stars)
    return dust, {"5★": stars.count(5), "4★": stars.count(4), "3★": stars.count(3)}
