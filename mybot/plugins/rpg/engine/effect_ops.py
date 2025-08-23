# mybot/plugins/rpg/engine/effect_ops.py
from typing import Callable, Dict, Any

# 目标实体需具备以下接口（见下方“实体接口约定”）：
# - take_damage(amount:int, source)->int(实际伤害)
# - heal(amount:int, source)
# - add_stat_pct(stat:str, value:int/float)
# - add_buff(buff_id:str, stacks:int, source)
# - dispel(count:int, positive:bool)
# - try_crit()->bool


def op_damage(
    eff: Dict[str, Any], ctx, target, scope, eval_fn: Callable[[str, dict], float]
):
    power_expr = eff.get("power", "0")
    amount = int(max(0, eval_fn(power_expr, scope)))
    # 暴击
    if eff.get("crit", False) and ctx.caster.try_crit():
        amount = int(amount * 1.5)
        ctx.payload["last_crit"] = True
    else:
        ctx.payload["last_crit"] = False
    dealt = target.take_damage(amount, source=ctx.caster)
    ctx.payload["last_damage"] = dealt  # 给后续效果（比如 leech）用


def op_heal(eff, ctx, target, scope, eval_fn):
    amount = int(max(0, eval_fn(eff.get("power", "0"), scope)))
    target.heal(amount, source=ctx.caster)
    ctx.payload["last_heal"] = amount


def op_leech(eff, ctx, target, scope, eval_fn):
    ratio = float(eff.get("ratio", 0))
    last = int(ctx.payload.get("last_damage", 0))
    if last > 0 and ratio > 0:
        ctx.caster.heal(int(last * ratio), source=ctx.caster)


def op_stat_pct(eff, ctx, target, scope, eval_fn):
    stat = eff["stat"].upper()
    val = float(eff["value"])
    target.add_stat_pct(stat, val)


def op_add_buff(eff, ctx, target, scope, eval_fn):
    buff_id = eff["buff_id"]
    stacks = int(eff.get("stacks", 1))
    target.add_buff(buff_id, stacks, source=ctx.caster)


def op_dispel(eff, ctx, target, scope, eval_fn):
    target.dispel(
        count=int(eff.get("count", 1)), positive=bool(eff.get("positive", True))
    )


EFFECT_OPS = {
    "damage": op_damage,
    "heal": op_heal,
    "leech": op_leech,
    "stat_pct": op_stat_pct,
    "add_buff": op_add_buff,
    "dispel": op_dispel,
}
