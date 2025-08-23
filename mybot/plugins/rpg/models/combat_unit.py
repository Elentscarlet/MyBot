from abc import ABC, abstractmethod
class CombatUnit(ABC):
    """战斗单位基类"""

    def __init__(self):
        self.points = {"str": 0, "def": 0, "hp": 0, "agi": 0, "int": 0, "crit": 0}
        self.current_hp = 0

    @property
    def max_hp(self):
        return self.points["hp"] * 10

    @property
    def attack(self):
        return self.points["str"] * 2

    @property
    def defense(self):
        return self.points["def"] * 1.5

    @property
    def agility(self):
        return self.points["agi"]

    @property
    def critical_rate(self):
        return self.points["crit"] * 0.02