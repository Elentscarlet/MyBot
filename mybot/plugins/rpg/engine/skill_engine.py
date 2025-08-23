# mybot/plugins/rpg/engine/skill_engine.py
from __future__ import annotations
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
import random
import math
import pathlib
import yaml

from .effect_ops import EFFECT_OPS
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
    def match_equip_rules(self, score: int) -> List[str]:
        """根据 score 按 equip.yaml 产出技能 ID 列表（按出现顺序去重累积）。"""
        out: List[str] = []
        seen = set()
        for r in self.equip_rules:
            cond = r.get("when", {})
            gte = int(cond.get("score_gte", -(10**9)))
            lte = int(cond.get("score_lte", 10**9))
            if gte <= score <= lte:
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

    # ---------- 事件分发 ----------
    def emit(self, event: str, actor: Entity, payload: Optional[Dict[str, Any]] = None):
        """统一事件入口：依技能/BUFF的 trigger 与 tick_trigger 执行 effects。"""
        ctx = Context(
            caster=actor,
            targets=[actor],
            event=event,
            payload=payload or {},
            rng=self.rng,
        )

        # 1) 技能被动/光环等
        for s in getattr(actor, "skills", []):
            if getattr(s, "trigger", None) == event:
                tlist = self._resolve_targets(actor, getattr(s, "target", "self"))
                self._run_effects(getattr(s, "effects", []), ctx, tlist)

        # 2) BUFF 即时触发（非 tick）
        for buff in list(getattr(actor, "buffs", {}).values()):
            bdef = self.buff_defs.get(buff.buff_id, {})
            if bdef.get("trigger") == event:
                tlist = self._resolve_targets(actor, bdef.get("target", "self"))
                self._run_effects(
                    bdef.get("effects", []), ctx, tlist, stacks=buff.stacks
                )

    def cast(
        self, actor: Entity, skill_id: str, target_spec: Optional[str] = None
    ) -> bool:
        """释放一个主动技：外层保证 cost/cd 校验与扣除。这里做 on_before_skill 与 on_cast。"""
        s = self.build_skill_from_id(skill_id)
        if not s:
            return False
        # 预热（可被动加伤/降耗等）
        self.emit("on_before_skill", actor, payload={"skill_id": skill_id})
        # 施放
        tgt_spec = target_spec or s.target
        targets = self._resolve_targets(actor, tgt_spec)
        ctx = Context(
            caster=actor,
            targets=targets,
            event="on_cast",
            payload={"skill_id": skill_id},
            rng=self.rng,
        )
        self._run_effects(getattr(s, "effects", []), ctx, targets)
        self.log.append(f"{actor.name} 使用 {s.name}")
        return True

    def tick_buffs(self, actor: Entity):
        """处理带 tick_trigger 的 BUFF（持续回合递减，过期移除）。"""
        for buff in list(getattr(actor, "buffs", {}).values()):
            bdef = self.buff_defs.get(buff.buff_id, {})
            tick_tr = bdef.get("tick_trigger")
            if tick_tr in ("on_turn_start", "on_turn_end"):
                base_ctx = Context(
                    caster=actor,
                    targets=[actor],
                    event=tick_tr,
                    payload={"buff_id": buff.buff_id},
                    rng=self.rng,
                )
                self._run_effects(
                    bdef.get("tick_effects", []), base_ctx, [actor], stacks=buff.stacks
                )
                buff.remaining_turns -= 1
                if buff.remaining_turns <= 0:
                    actor.remove_buff(buff.buff_id, reason="expired")
                    self.log.append(f"{actor.name} 的 {buff.buff_id} 到期")

    # ---------- 内部：执行效果 ----------
    def _run_effects(
        self, effects, ctx: Context, targets: List[Entity], stacks: int = 1
    ):
        # 每条效果依次对所有目标执行；可利用 ctx.payload 传递链路信息（如 last_damage）
        ctx.payload.pop("last_damage", None)
        for eff in effects or []:
            impl = EFFECT_OPS.get(eff.get("op"))
            if not impl:
                continue
            for t in targets:
                impl(eff, ctx, t, self._scope(ctx, t, stacks), Formula.eval)

    def _scope(
        self, ctx: Context, target: Optional[Entity], stacks: int
    ) -> Dict[str, Any]:
        c = ctx.caster
        tgt = target or c
        return {
            "ATK": c.stats.ATK,
            "DEF": c.stats.DEF,
            "AGI": c.stats.AGI,
            "INT": c.stats.INT,
            "CRIT": c.stats.CRIT,  # 0~1
            "HP": tgt.stats.HP,
            "MAX_HP": tgt.stats.MAX_HP,
            "incoming": ctx.payload.get("incoming", {}),
            "STKS": stacks,  # 当前 Buff 层数；表里可写 "ATK*0.1*STKS"
        }

    # ---------- 目标解析 ----------
    def _resolve_targets(self, actor: Entity, spec: str) -> List[Entity]:
        spec = (spec or "self").lower()
        if spec in ("self", "ally_self"):
            return [actor]
        if spec in ("enemy_single", "enemy"):
            tgt = actor.pick_enemy_single(self.rng)
            return [tgt] if tgt else []
        if spec in ("enemy_all", "enemies_all"):
            return actor.list_enemies()
        if spec in ("ally_lowest_hp",):
            tgt = actor.pick_ally_lowest_hp()
            return [tgt] if tgt else [actor]
        if spec in ("ally_all", "allies_all"):
            return [a for a in actor._allies if a.is_alive()]
        # 兜底
        return [actor]
