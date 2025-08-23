from typing import List

# 获取评级文字
def slots_to_rank(slots: List[int]) -> str:
    return "".join({1: "C", 2: "B", 3: "A", 4: "S"}[x] for x in slots)

# 获取精炼消耗
def refine_cost(next_val: int) -> int:
    return {2: 100, 3: 300, 4: 900}.get(next_val, 999999)

# 获取评分
def score_of_slots(slots: List[int]) -> int:
    return int(slots[0] * 1 + slots[1] * 2 + slots[2] * 3)

# 武器类
class Weapon:
    def __init__(self):
        self.name = "武器名称"
        self.slots = [1, 1, 1] #C 1 B 2 A 3 S 4

    def score_of_slots(self) -> int:
        return score_of_slots(self.slots)

    def slots_to_rank(self) -> str:
        return slots_to_rank(self.slots)
