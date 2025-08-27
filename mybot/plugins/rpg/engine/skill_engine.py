# mybot/plugins/rpg/engine/skill_engine.py
from __future__ import annotations
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
import random
import math
import pathlib
import yaml

from ..battle.entity import Entity


# ===== 基础：上下文与表达式求值 =====
@dataclass
class Context:
    caster: Entity
    targets: List[Entity]
    event: str
    payload: Dict[str, Any]
    rng: random.Random


class Formula:
    """极简安全求值器：仅开放常用内建与传入scope变量。"""

    _SAFE_FUNCS = {
        "abs": abs,
        "max": max,
        "min": min,
        "int": int,
        "float": float,
        "round": round,
        "sqrt": math.sqrt,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    @staticmethod
    def eval(expr: str, scope: Dict[str, Any]) -> Any:
        return eval(expr, {"__builtins__": {}}, {**Formula._SAFE_FUNCS, **scope})


# ===== 技能引擎主体 =====
class SkillEngine:
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        root = pathlib.Path(__file__).resolve().parent.parent  # .../rpg
        self._skills_path = root / "data" / "skills.yaml"
        self._buffs_path = root / "data" / "buffs.yaml"
        self._equip_path = root / "data" / "equip.yaml"

        # 载入配表
        self.skill_defs: Dict[str, Dict[str, Any]] = {}
        self.buff_defs: Dict[str, Dict[str, Any]] = {}
        self.equip_rules: List[Dict[str, Any]] = []
        self._load_tables()

        # 简单日志（可被 handlers 读取）
        self.log: List[str] = []

    # ---------- 表加载 ----------
    def _load_tables(self):
        if self._skills_path.exists():
            skills = yaml.safe_load(self._skills_path.read_text(encoding="utf-8")) or []
            self.skill_defs = {
                s["id"]: s for s in skills if isinstance(s, dict) and "id" in s
            }
        if self._buffs_path.exists():
            buffs = yaml.safe_load(self._buffs_path.read_text(encoding="utf-8")) or []
            self.buff_defs = {
                b["id"]: b for b in buffs if isinstance(b, dict) and "id" in b
            }
        if self._equip_path.exists():
            equip = yaml.safe_load(self._equip_path.read_text(encoding="utf-8")) or {}
            self.equip_rules = list(equip.get("rules", []))

    # ---------- 装备→技能规则 ----------
    def match_equip_rules_by_points(self, points) -> List[str]:
        """
        根据玩家属性 points 匹配技能ID列表。
        points: 支持对象（有 .str/.agi/...）或 dict
        """
        out: list[str] = []
        seen = set()
        for r in self.equip_rules:
            cond = r.get("when", {})
            ok = True
            for k, v in cond.items():
                if k.endswith("_gte"):
                    attr = k[:-4]
                    val = getattr(points, attr, None)
                    if val is None or val < v:
                        ok = False
                        break
            if ok:
                for sid in r.get("give", []):
                    if sid not in seen:
                        out.append(sid)
                        seen.add(sid)
        return out

    # ---------- 构造运行时技能 ----------
    def build_skill_from_id(self, sid: str):
        d = self.skill_defs.get(sid)
        if not d:
            return None
        # 只抽取运行期必需字段；其余保持原样可在 effects 中读取
        return SimpleNamespace(
            id=d["id"],
            name=d.get("name", d["id"]),
            type=d.get("type", "active"),
            trigger=d.get("trigger", "on_cast"),
            target=d.get("target", "self"),
            effects=list(d.get("effects", [])),
            cd=int(d.get("cd", 0)),
            cost=d.get("cost", {}),  # 由管理层处理
        )
