from typing import Dict

from .weapon import Weapon
from mybot.plugins.rpg.storage import today_tag, load_players, save_players


def get_player(uid: str, gid: str, name: str):
    players = load_players()
    key = f"{gid}:{uid}"
    player_data = players.get(key)

    if not player_data:
        player = Player(uid, gid, name)
        players[key] = player.to_dict()
        save_players(players)
    else:
        player = Player.from_dict(player_data)
        if player.counters["daily_date"] != today_tag():
            player.reset_daily_counters()
            players[key] = player.to_dict()
            save_players(players)

    return player


def put_player(player: "Player") -> None:
    """保存玩家到存储"""
    players = load_players()
    key = f"{player.gid}:{player.uid}"
    players[key] = player.to_dict()
    save_players(players)


class Player:
    def __init__(self, uid: str, gid: str, name: str):
        super().__init__()
        self.uid = uid
        self.gid = gid
        self.name = name
        self.points = {"str": 0, "def": 0, "hp": 0, "agi": 0, "int": 0, "crit": 0}
        self.weapon = Weapon()
        # 养成
        self.dust = 0
        # 抽卡
        self.diamond = 0
        # 属性点养成
        self.tear = 0
        self.counters = {
            "daily_date": today_tag(),
            "free_explore_used": 0,
            "boss_hits": 0,
            "signed": False,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Player":
        """从字典创建Player实例"""
        player = cls(data["uid"], data["gid"], data["name"])
        player.points = data["points"]
        player.weapon = data["weapon"]
        player.dust = data["dust"]
        player.diamond = data["diamond"]
        player.tear = data["tear"]
        player.ticket = data["ticket"]
        player.counters = data["counters"]
        return player

    def to_dict(self) -> Dict:
        """将Player实例转换为字典"""
        return {
            "uid": self.uid,
            "gid": self.gid,
            "name": self.name,
            "points": self.points,
            "weapon": self.weapon,
            "dust": self.dust,
            "diamond": self.diamond,
            "tear": self.tear,
            "counters": self.counters,
        }

    def reset_daily_counters(self):
        """重置每日计数器"""
        self.counters = {
            "daily_date": today_tag(),
            "free_explore_used": 0,
            "boss_hits": 0,
            "signed": False,
        }

    def save(self):
        players = load_players()
        key = f"{self.gid}:{self.uid}"
        players[key] = self.to_dict()
        save_players(players)
