class Player:
    def __init__(self, weapon):
        self.assets = {
            # 抽卡道具
            'primogems': 0,
            'stone': 0,
            'heart': 0,
            'dust': 0
        }
        self.attributes = {
            'strength': 1,
            'defense': 0,
            'health': 0,
            'agility': 0,
            'intelligence': 0,
            'crit': 0
        }
        self.weapon = weapon

    def set_attribute_points(self, attr, points):
        self.attributes[attr] = points
