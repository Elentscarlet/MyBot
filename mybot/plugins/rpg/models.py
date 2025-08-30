# mybot/plugins/rpg/models.py
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from .storage import today_tag, load_players, save_players, load_boss_map, save_boss_map
from .util.config_loader import ConfigLoader

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

    def refine(self, p: Player) -> tuple[bool, str, int]:
        cost = self.cal_dust_consume()
        if cost > p.dust:
            return False, f"「粉尘不足」需要{cost}个粉尘✨才能精炼。\n当前武器：Lv.{self.rank}｜评分：{self.score}｜持有粉尘：{p.dust}✨", 0
        p.dust -= cost
        # 权重设置：数字越大，权重越小
        weights_matrix = [
            [45, 47, 48],
            [49, 49, 49],
            [5, 3, 2.5],
            [1, 1, 0.5]
        ]
        weights_array = np.array(weights_matrix)
        random_list = []
        for i in range(3):
            result = random.choices([1, 2, 3, 4], weights=weights_array[:, i], k=1)[0]
            random_list.append(result)
        new_score = slots_score(random_list)
        if new_score > self.score:
            self.slots = random_list
            return True, f"「精炼成功」！武器等级：{self.rank}｜评分{self.score}｜剩余粉尘{p.dust}✨|本次精炼消耗粉尘：{cost}✨", cost
        else:
            return False, f"「精炼失败」！武器等级：{self.rank}｜评分{self.score}｜剩余粉尘{p.dust}✨|本次精炼消耗粉尘：{cost}✨", cost

    @staticmethod
    def from_dict(d: Dict) -> "Weapon":
        return Weapon(d.get("name", "无名之刃"), list(d.get("slots", [1, 1, 1])))

    def to_dict(self) -> Dict:
        return {"name": self.name, "slots": self.slots}

    def cal_dust_consume(self):
        return 30


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
class Pconfig:
    # 模式：完整版(0) 精简版(1) 仅结果(2)
    battle_report_model: int = 0

    @staticmethod
    def from_dict(d: Dict) -> "Pconfig":
        return Pconfig(
            d.get("battle_report_model", 0),
        )

    def to_dict(self) -> Dict:
        return {
            "battle_report_model": self.battle_report_model
        }


@dataclass
class Player:
    uid: str
    gid: str
    name: str
    level: int = 1
    unspent: int = 0
    points: Points = field(default_factory=Points)
    extra_points: Points = field(default_factory=lambda: Points(str=0, def_=0, hp=0, agi=0, crit=0))
    weapon: Weapon = field(default_factory=Weapon)
    dust: int = 0
    diamond: int = 0
    tear: int = 0
    counters: Counters = field(default_factory=Counters.today)
    config: Pconfig = field(default_factory=Pconfig)
    skills: Dict[str, int] = field(default_factory=dict)
    equipped_skills: List[str] = field(default_factory=list)

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
            extra_points=Points.from_dict(d.get("extra_points", {})),
            weapon=Weapon.from_dict(d.get("weapon", {})),
            dust=d.get("dust", 0),
            diamond=d.get("diamond", 0),
            tear=d.get("tear", 0),
            counters=Counters.from_dict(d.get("counters", {})),
            config=Pconfig.from_dict(d.get("config", {})),
            skills=d.get("skills", {}),
            equipped_skills=d.get("equipped_skills", []),
        )

    def to_dict(self) -> Dict:
        return {
            "uid": self.uid,
            "gid": self.gid,
            "name": self.name,
            "level": self.level,
            "unspent": self.unspent,
            "points": self.points.to_dict(),
            "extra_points": self.extra_points.to_dict(),
            "weapon": self.weapon.to_dict(),
            "dust": self.dust,
            "diamond": self.diamond,
            "tear": self.tear,
            "counters": self.counters.to_dict(),
            "config": self.config.to_dict(),
            "skills": self.skills,
            "equipped_skills": self.equipped_skills
        }

    def extra_distribute(self, attribute: str):
        if attribute == "力量":
            self.extra_points.str += 1
        elif attribute == "防御":
            self.extra_points.def_ += 1
        elif attribute == "体力":
            self.extra_points.hp += 1
        elif attribute == "敏捷":
            self.extra_points.agi += 1
        elif attribute == "暴击":
            self.extra_points.crit += 1
        else:
            pass
        self.tear = max(self.tear - 1, 0)
        put_player(self)

    def get_profile(self) -> str:
        detail = []

        # 标题
        detail.append(f"【 {self.name} 的角色面板 】")

        # 武器区域
        detail.append(f"╭─ 武器 ─{'─' * 7}")
        detail.append(f"│ {self.weapon.name} {self.weapon.rank}级")
        detail.append(f"│ 评分: {self.weapon.score}")
        detail.append(f"│ 技能: {get_equipped_skill_names(player=self)}")

        # 属性区域
        detail.append(f"╭─ 属性 ─{'─' * 7}")
        detail.append(f"│ 力量: {self.points.str}(+{self.extra_points.str})")
        detail.append(f"│ 防御: {self.points.def_}(+{self.extra_points.def_})")
        detail.append(f"│ 体力: {self.points.hp}(+{self.extra_points.hp})")
        detail.append(f"│ 敏捷: {self.points.agi}(+{self.extra_points.agi})")
        detail.append(f"│ 暴击: {self.points.crit}(+{self.extra_points.crit})")

        # 资源区域
        detail.append(f"╭─ 资源 ─{'─' * 7}")
        detail.append(f"│ 粉尘: {self.dust}✨")
        detail.append(f"│ 钻石: {self.diamond}💎")
        detail.append(f"│ 女神之泪: {self.tear}💧")

        # 活动区域
        detail.append(f"╭─ 活动 ─{'─' * 7}")
        detail.append(f"│ 远征: {self.counters.free_explore_used}/2")
        detail.append(f"│ 出刀: {self.counters.boss_hits}/3")
        detail.append(f"│ 签到: {'✅' if self.counters.signed else '❌'}")

        return "\n".join(detail)

    def get_point_detail(self) -> str:
        detail = [f"力量: {self.points.str}(+{self.extra_points.str})",
                  f" │ 防御: {self.points.def_}(+{self.extra_points.def_})",
                  f" │ 体力: {self.points.hp}(+{self.extra_points.hp})",
                  f" │ 敏捷: {self.points.agi}(+{self.extra_points.agi})",
                  f" │ 暴击: {self.points.crit}(+{self.extra_points.crit})"]
        return "".join(detail)


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


def get_players_by_gid(gid: str) -> List[Player]:
    list_players = []
    db = load_players()
    for item in db.values():
        p = Player.from_dict(item)
        if p.gid == gid:
            list_players.append(p)
    return list_players


def get_skill(player: Player, skill_id: str, skill_map: Dict[str, Dict]) -> Tuple[bool, str]:
    # 如果玩家已经拥有这个技能
    if skill_id in player.skills.keys():
        return False, f"玩家已经拥有技能[{skill_map.get(skill_id).get("name")}]"

    # 如果技能槽未满（小于等于3个）
    if len(player.skills) < 3:
        player.skills.__setitem__(skill_id, 1)
        put_player(player)
        return True, f"技能[{skill_map.get(skill_id).get("name")}]获取成功"

    # 如果技能槽已满（超过5个）
    else:
        # 找出未装备的技能进行替换
        replaceable_skills = []
        for skill_id_in_dict in player.skills.keys():
            # 假设 player 有一个 equipped_skills 属性来存储已装备的技能名称列表
            if skill_id_in_dict in player.equipped_skills:
                continue  # 跳过已装备的技能
            replaceable_skills.append(skill_id_in_dict)

        # 如果没有可替换的技能（所有技能都已装备）
        if not replaceable_skills:
            return False, "所有技能都已装备，无法替换，请先卸下某个技能"

        # 替换第一个可替换的技能（或者你可以实现更复杂的替换逻辑）
        skill_to_remove = replaceable_skills[0]
        player.skills.pop(skill_to_remove)
        player.skills.__setitem__(skill_id, 1)

        put_player(player)

        return True, f"已遗忘技能[{skill_map.get(skill_to_remove).get("name")}]，并成功学习[{skill_map.get(skill_id).get("name")}]"


def equip_skill(player: Player, skill_id: str, skill_map: Dict[str, Dict]) -> Tuple[bool, str]:
    # 检查玩家是否拥有该技能
    if skill_id not in player.skills.keys():
        return False, f"未学习技能[{skill_map.get(skill_id).get("name")}]，无法装配"

    # 初始化 equipped_skills 属性（如果不存在）
    if not hasattr(player, 'equipped_skills'):
        player.equipped_skills = []

    # 检查技能是否已经装备
    if skill_id in player.equipped_skills:
        return False, f"技能[{skill_map.get(skill_id).get("name")}]已经装配"

    # 检查装备槽位限制（假设最多可以装备3个技能）
    max_equipped = 1
    if len(player.equipped_skills) >= max_equipped:
        old_skill_id = player.equipped_skills.pop(0)
        player.equipped_skills.append(skill_id)
        put_player(player)
        return True, f"装备槽已满（最多{max_equipped}个），已自动卸下技能[{skill_map.get(old_skill_id).get("name")}]，技能[{skill_map.get(skill_id).get("name")}]装配成功"

    # 装备技能
    player.equipped_skills.append(skill_id)

    put_player(player)

    return True, f"技能[{skill_map.get(skill_id).get("name")}]装配成功"


def level_up_skill(player: Player, skill_id: str, skill_map: Dict[str, Dict]) -> Tuple[bool, str]:
    # 检查玩家是否拥有该技能
    if skill_id not in player.skills.keys():
        return False, f"未学习技能[{skill_map.get(skill_id).get("name")}]，无法升级"

    # 装备技能
    player.skills[skill_id] += 1
    put_player(player)

    return True, f"技能[{skill_map.get(skill_id).get("name")}]升级成功，当前等级:{player.skills[skill_id]}"


def forget_skill(player: Player, skill_id: str, skill_map: Dict[str, Dict]) -> Tuple[bool, str]:
    if skill_id not in player.skills.keys():
        return False, f"你愣了一下，好像你本来就不会这个技能"

    player.skills.pop(skill_id)
    put_player(player)
    return True, f"技能[{skill_map.get(skill_id).get("name")}]已被成功遗忘，相关的记忆也随之消散..."


def get_equipped_skill_names(player: Player) -> str:
    config_loader = ConfigLoader()
    skills_map = config_loader.get_skills_map(True)
    equipped_skill_names = []
    for skill_id in player.equipped_skills:
        name = skills_map.get(skill_id).get("name")
        equipped_skill_names.append(name)
    if len(equipped_skill_names) == 0:
        return "无"
    return ",".join(equipped_skill_names)


def put_players(players: List[Player]):
    db = load_players()
    for p in players:
        db[f"{p.gid}:{p.uid}"] = p.to_dict()
    save_players(db)


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
