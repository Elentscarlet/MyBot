# mybot/plugins/rpg/engine/skill_engine.py
import os, yaml, random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from .effect_ops import EFFECT_OPS


@dataclass
class Context:
    caster: "Entity"
    targets: List["Entity"]
    event: str
    payload: Dict[str, Any]  # 事件数据，如 incoming.damage
    rng: random.Random


class Formula:
    SAFE_FUNCS = {"min": min, "max": max, "abs": abs, "int": int, "round": round}
    VARS = {"ATK", "DEF", "HP", "MAX_HP", "AGI", "INT", "CRIT", "incoming", "STKS"}

    @staticmethod
    def eval(expr: str, scope: dict):
        safe_globals = {"__builtins__": {}}
        loc = {k: v for k, v in scope.items() if k in Formula.VARS}
        loc.update(Formula.SAFE_FUNCS)
        return eval(expr, safe_globals, loc)


class TargetResolver:
    @staticmethod
    def resolve(target_def: Dict[str, Any], ctx: Context):
        sel = target_def["select"]
        if sel == "self":
            return [ctx.caster]
        if sel == "enemy.single":
            return [ctx.caster.pick_enemy_single(ctx.rng)]
        if sel == "enemy.all":
            return ctx.caster.list_enemies()
        if sel == "enemy.random":
            n = int(target_def.get("n", 1))
            pool = ctx.caster.list_enemies()
            ctx.rng.shuffle(pool)
            return pool[:n]
        if sel == "ally.lowest_hp":
            return [ctx.caster.pick_ally_lowest_hp()]
        if sel == "context.source":
            s = ctx.payload.get("source")
            return [s] if s else []
        return []


class SkillEngine:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.skills = {}  # id->def
        self.buffs = {}  # id->def
        self.targets = {}  # id->def
        self.index = {}  # trigger-> [skill_id]
        self.rng = random.Random()
        self.reload()

    def reload(self):
        self.skills = self._load_yaml("skills.yaml")
        self.buffs = self._load_yaml("buffs.yaml")
        self.targets = self._load_yaml("targets.yaml")
        self.skills = {s["id"]: s for s in self.skills}
        self.buffs = {b["id"]: b for b in self.buffs}
        # 触发索引
        self.index.clear()
        for s in self.skills.values():
            trig = s["trigger"]
            self.index.setdefault(trig, []).append(s["id"])

    def _load_yaml(self, filename: str):
        p = os.path.join(self.data_dir, filename)
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or []

    # ========== 事件入口 ==========
    def on_event(
        self, event: str, caster: "Entity", payload: Optional[Dict[str, Any]] = None
    ):
        payload = payload or {}
        ctx = Context(
            caster=caster, targets=[], event=event, payload=payload, rng=self.rng
        )
        for sid in self.index.get(event, []):
            sdef = self.skills[sid]
            if not self._conditions_ok(
                sdef.get("conditions", []), ctx, target=None, stks=1
            ):
                continue
            tdef = self.targets[sdef["target"]]
            targets = TargetResolver.resolve(tdef, ctx)
            self._run_effects(sdef.get("effects", []), ctx, targets)

    # ========== Buff Tick（在战斗循环里调） ==========
    def tick_buffs(self, event: str, entity: "Entity"):
        # 逐个 Buff 执行 tick_effects，并衰减持续回合
        for buff in list(entity.buffs):
            bdef = self.buffs.get(buff.buff_id)
            if not bdef:
                continue
            if bdef.get("tick_trigger") == event:
                base_ctx = Context(
                    caster=entity,
                    targets=[entity],
                    event=event,
                    payload={"buff_id": buff.buff_id},
                    rng=self.rng,
                )
                self._run_effects(
                    bdef.get("tick_effects", []), base_ctx, [entity], stacks=buff.stacks
                )
                buff.remaining_turns -= 1
                if buff.remaining_turns <= 0:
                    entity.remove_buff(buff.buff_id, reason="expired")

    # ========== 内部：条件/执行/作用域 ==========
    def _conditions_ok(self, conds, ctx: Context, target, stks: int):
        for c in conds:
            if not Formula.eval(c["expr"], self._scope(ctx, target, stks)):
                return False
        return True

    def _run_effects(
        self, effects, ctx: Context, targets: List["Entity"], stacks: int = 1
    ):
        # 每条效果依次对所有目标执行；可利用 ctx.payload 传递链路信息（如 last_damage）
        ctx.payload.pop("last_damage", None)
        for eff in effects:
            impl = EFFECT_OPS.get(eff["op"])
            if not impl:
                continue
            for t in targets:
                impl(eff, ctx, t, self._scope(ctx, t, stacks), Formula.eval)

    def _scope(self, ctx: Context, target: Optional["Entity"], stacks: int):
        c = ctx.caster
        tgt = target or c
        return {
            "ATK": c.stats.ATK,
            "DEF": c.stats.DEF,
            "AGI": c.stats.AGI,
            "INT": c.stats.INT,
            "CRIT": c.stats.CRIT,
            "HP": tgt.stats.HP,
            "MAX_HP": tgt.stats.MAX_HP,
            "incoming": ctx.payload.get("incoming", {}),
            "STKS": stacks,  # 当前 Buff 层数，表里可以写 "ATK*0.1*STKS"
        }
