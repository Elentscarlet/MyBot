from mybot.plugins.rpg.models.combat_unit import CombatUnit


class Monster(CombatUnit):
    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def get_monster(self):
        return self