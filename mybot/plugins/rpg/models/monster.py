class Monster:
    def __init__(self, name: str):
        self.points = {"str": 0, "def": 0, "hp": 0, "agi": 0, "int": 0, "crit": 0}
        self.name = name

    def get_monster(self):
        return self