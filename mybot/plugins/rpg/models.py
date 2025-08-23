# mybot/plugins/rpg/models.py
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Dict, List
from .storage import today_tag, load_players, save_players, load_boss_map, save_boss_map

RANK_VAL = {"C": 1, "B": 2, "A": 3, "S": 4}
VAL_RANK = {v: k for k, v in RANK_VAL.items()}


def slots_score(slots: List[int]) -> int:
    # 1/2/3 位权重
    return int(slots[0] * 1 + slots[1] * 2 + slots[2] * 3)


def slots_rank(slots: List[int]) -> str:
    return "".join({1: "C", 2: "B", 3: "A", 4: "S"}[x] for x in slots)


def refine_cost(next_val: int) -> int:
    return {2: 100, 3: 300, 4: 900}.get(next_val, 999999)


@dataclass
class Points:
    str: int = 8
    def_: int = 6  # 注意字段名从 def -> def_，防止关键字冲突
    hp: int = 6
    agi: int = 6
    crit: int = 0

    @staticmethod
    def default():
        # 固定模板：力量8、防御6、体力6、敏捷6、暴击0（总计26点）
        return Points(str=8, def_=6, hp=6, agi=6, crit=0)

    @staticmethod
    def from_dict(d: Dict) -> "Points":
        return Points(
            d.get("str", 0),
            d.get("def", d.get("def_", 0)),
            d.get("hp", 0),
            d.get("agi", 0),
            d.get("crit", 0),
        )

    def to_dict(self) -> Dict:
        return {
            "str": self.str,
            "def": self.def_,
            "hp": self.hp,
            "agi": self.agi,
            "crit": self.crit,
        }


@dataclass
class Weapon:
    name: str = "无名之刃"
    slots: List[int] = field(default_factory=lambda: [1, 1, 1])  # C=1 B=2 A=3 S=4

    @property
    def score(self) -> int:
        return slots_score(self.slots)

    @property
    def rank(self) -> str:
        return slots_rank(self.slots)

    def refine(self, idx: int, dust_wallet: Dict[str, int]) -> str:
        """idx: 1/2/3；dust_wallet 提供 { "dust": 当前粉尘 } 并就地扣减"""
        if idx not in (1, 2, 3):
            return "槽位只支持 1/2/3"
        cur = self.slots[idx - 1]
        if cur >= 4:
            return "该槽位已是S"
        nxt = cur + 1
        cost = refine_cost(nxt)
        if dust_wallet["dust"] < cost:
            return f"粉尘不足，需要{cost}"
        dust_wallet["dust"] -= cost
        self.slots[idx - 1] = nxt
        return f"精炼成功：{self.rank}｜评分{self.score}｜粉尘{dust_wallet['dust']}"

    @staticmethod
    def from_dict(d: Dict) -> "Weapon":
        return Weapon(d.get("name", "无名之刃"), list(d.get("slots", [1, 1, 1])))

    def to_dict(self) -> Dict:
        return {"name": self.name, "slots": self.slots}


@dataclass
class Counters:
    daily_date: str
    free_explore_used: int = 0
    boss_hits: int = 0
    signed: bool = False

    @staticmethod
    def today() -> "Counters":
        return Counters(today_tag(), 0, 0, False)

    @staticmethod
    def from_dict(d: Dict) -> "Counters":
        tag = d.get("daily_date", today_tag())
        c = Counters(
            tag,
            d.get("free_explore_used", 0),
            d.get("boss_hits", 0),
            d.get("signed", False),
        )
        # 跨天刷新
        if c.daily_date != today_tag():
            c = Counters.today()
        return c

    def to_dict(self) -> Dict:
        return {
            "daily_date": self.daily_date,
            "free_explore_used": self.free_explore_used,
            "boss_hits": self.boss_hits,
            "signed": self.signed,
        }


@dataclass
class Player:
    uid: str
    gid: str
    name: str
    level: int = 1
    unspent: int = 0
    points: Points = field(default_factory=Points)
    weapon: Weapon = field(default_factory=Weapon)
    dust: int = 0
    diamond: int = 0
    tear: int = 0
    ticket: int = 0
    counters: Counters = field(default_factory=Counters.today)

    # ---- 兼容层（短期让 p["diamond"] 还能用）----
    def __getitem__(self, k: str):
        if k == "points":
            return self.points.to_dict()
        if k == "weapon":
            return self.weapon.to_dict()
        if k == "counters":
            return self.counters.to_dict()
        return getattr(self, k)

    def __setitem__(self, k: str, v):
        if k == "points":
            self.points = Points.from_dict(v)
            return
        if k == "weapon":
            self.weapon = Weapon.from_dict(v)
            return
        if k == "counters":
            self.counters = Counters.from_dict(v)
            return
        setattr(self, k, v)

    @staticmethod
    def from_dict(d: Dict) -> "Player":
        return Player(
            uid=d["uid"],
            gid=d["gid"],
            name=d.get("name", d["uid"]),
            level=d.get("level", 1),
            unspent=d.get("unspent", 0),
            points=Points.from_dict(d.get("points", {})),
            weapon=Weapon.from_dict(d.get("weapon", {})),
            dust=d.get("dust", 0),
            diamond=d.get("diamond", 0),
            tear=d.get("tear", 0),
            ticket=d.get("ticket", 0),
            counters=Counters.from_dict(d.get("counters", {})),
        )

    def to_dict(self) -> Dict:
        return {
            "uid": self.uid,
            "gid": self.gid,
            "name": self.name,
            "level": self.level,
            "unspent": self.unspent,
            "points": self.points.to_dict(),
            "weapon": self.weapon.to_dict(),
            "dust": self.dust,
            "diamond": self.diamond,
            "tear": self.tear,
            "ticket": self.ticket,
            "counters": self.counters.to_dict(),
        }


@dataclass
class Boss:
    gid: str
    boss_date: str
    name: str = "远古巨像"
    hp: int = 3000
    hp_max: int = 3000
    atk: int = 50
    def_: int = 15
    spd: int = 10
    crit: int = 10
    board: Dict[str, int] = field(default_factory=dict)
    killed: bool = False

    @staticmethod
    def today(gid: str) -> "Boss":
        return Boss(gid=gid, boss_date=today_tag())

    @staticmethod
    def from_dict(d: Dict) -> "Boss":
        b = Boss(
            gid=d["gid"],
            boss_date=d.get("boss_date", today_tag()),
            name=d.get("name", "远古巨像"),
            hp=d.get("hp", 3000),
            hp_max=d.get("hp_max", 3000),
            atk=d.get("atk", 50),
            def_=d.get("def", d.get("def_", 15)),
            spd=d.get("spd", 10),
            crit=d.get("crit", 10),
            board=d.get("board", {}),
            killed=d.get("killed", False),
        )
        if b.boss_date != today_tag():
            b = Boss.today(b.gid)
        return b

    def to_dict(self) -> Dict:
        return {
            "gid": self.gid,
            "boss_date": self.boss_date,
            "name": self.name,
            "hp": self.hp,
            "hp_max": self.hp_max,
            "atk": self.atk,
            "def": self.def_,
            "spd": self.spd,
            "crit": self.crit,
            "board": self.board,
            "killed": self.killed,
        }


# ---- 读写 API 保持函数名不变，但返回对象 ----
def get_player(uid: str, gid: str, name: str) -> Player:
    db = load_players()  # Dict[str, Dict]
    key = f"{gid}:{uid}"
    raw = db.get(key)
    if not raw:
        p = Player(uid=uid, gid=gid, name=name)
        db[key] = p.to_dict()
        save_players(db)
        return p
    p = Player.from_dict(raw)
    # 跨天 counters 刷新已经在 Counters.from_dict() 做了
    # 补全属性
    if not hasattr(p, "points") or p.points is None:
        p.points = Points()
    if not hasattr(p, "weapon") or p.weapon is None:
        p.weapon = Weapon()
    return p


def put_player(p: Player):
    db = load_players()
    db[f"{p.gid}:{p.uid}"] = p.to_dict()
    save_players(db)


def get_boss(gid: str) -> Boss:
    bm = load_boss_map()
    raw = bm.get(gid)
    if not raw:
        b = Boss.today(gid)
        bm[gid] = b.to_dict()
        save_boss_map(bm)
        return b
    b = Boss.from_dict(raw)
    if b.boss_date != today_tag():
        b = Boss.today(gid)
        bm[gid] = b.to_dict()
        save_boss_map(bm)
    return b


def put_boss(b: Boss):
    bm = load_boss_map()
    bm[b.gid] = b.to_dict()
    save_boss_map(bm)
