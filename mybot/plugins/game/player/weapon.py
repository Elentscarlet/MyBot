class Weapon:
    def __init__(self):
        self.level = 1
        # 磨损度 0~1
        self.wear = 0.0
        self.attributes  = {
            'strength': 1,
            'defense': 0,
            'health': 0,
            'agility': 0,
            'intelligence': 0,
            'crit':0
        }