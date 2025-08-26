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
        eff: Dict[str, Any],
        ctx: Any,
        target: Any,
        scope: Dict[str, Any],
        eval_fn: Callable[[str, Dict[str, Any]], Any],
) -> None:
    # 基础伤害表达式（必填）
    power_expr = eff.get("power", "0")
    base = float(eval_fn(power_expr, scope))

    # debug
    # print("[DEBUG] 怪物伤害scope:", scope)

    # 伤害随机波动（0~1，小数代表百分比）
    var = float(eff.get("variance", 0.0))
    if var > 0:
        import random

        jitter = 1.0 + random.uniform(-var, var)
        base *= jitter

    dmg = max(1, int(base))

    # 暴击（由实体提供 try_crit）
    can_crit = bool(eff.get("can_crit", False))
    if can_crit and hasattr(ctx.caster, "try_crit") and ctx.caster.try_crit():
        crit_multiplier = float(eff.get("crit_multiplier", 1.5))
        dmg = int(dmg * crit_multiplier)
        ctx.payload["crit"] = True

    # 扣血并记录“最后一次伤害”，便于后续效果读取
    dealt = target.cal_damage(dmg)

    # 新增：写入技能日志
    # 兼容 SkillEngine.log
    engine = getattr(ctx.caster, "engine", None)
    if engine and hasattr(engine, "log"):
        crit_str = "（暴击）" if ctx.payload.get("crit") else ""
        engine.log.append(
            f"{ctx.caster.name} 对 {target.name} 造成了 {dealt} 点伤害{crit_str}（剩余HP: {getattr(target, '_hp', '?')}）"
        )

    # 构建伤害事件payload
    payload = {
        'damage_amount': dealt,  # 初始造成的伤害
        'actual_damage': dealt,  # 实际造成的伤害
        'source': ctx.caster,
        'damage_type': 'physical',  # 可以根据需要扩展伤害类型
        'can_reflect': True
    }
    engine.emit('on_receive_damage', target, payload)

    ctx.payload["last_damage"] = dealt


def op_heal(
        eff: Dict[str, Any],
        ctx: Any,
        target: Any,
        scope: Dict[str, Any],
        eval_fn: Callable[[str, Dict[str, Any]], Any],
) -> None:
    amount = int(max(0, eval_fn(eff.get("power", "0"), scope)))
    target.heal(amount, source=ctx.caster)
    ctx.payload["last_heal"] = amount

    engine = getattr(ctx.caster, "engine", None)
    if engine and hasattr(engine, "log"):
        engine.log.append(
            f"{ctx.caster.name} 治疗了 {target.name} {amount} 点HP（当前HP: {getattr(target, '_hp', '?')}）"
        )


def op_leech(
        eff: Dict[str, Any],
        ctx: Any,
        target: Any,
        scope: Dict[str, Any],
        eval_fn: Callable[[str, Dict[str, Any]], Any],
) -> None:
    ratio = float(eff.get("ratio", 0))
    last = int(ctx.payload.get("last_damage", 0))
    if last > 0 and ratio > 0:
        heal_amount = int(last * ratio)
        ctx.caster.heal(heal_amount, source=ctx.caster)
        engine = getattr(ctx.caster, "engine", None)
        if engine and hasattr(engine, "log"):
            engine.log.append(
                f"{ctx.caster.name} 吸血回复了 {heal_amount} 点HP（当前HP: {getattr(ctx.caster, '_hp', '?')}）"
            )


def op_stat_pct(
        eff: Dict[str, Any],
        ctx: Any,
        target: Any,
        scope: Dict[str, Any],
        eval_fn: Callable[[str, Dict[str, Any]], Any],
) -> None:
    stat = eff["stat"].upper()
    val = float(eff["value"])
    target.add_stat_pct(stat, val)
    engine = getattr(ctx.caster, "engine", None)
    if engine and hasattr(engine, "log"):
        engine.log.append(f"{target.name} 获得了 {stat} +{val * 100:.0f}% 的加成")


def op_add_buff(
        eff: Dict[str, Any],
        ctx: Any,
        target: Any,
        scope: Dict[str, Any],
        eval_fn: Callable[[str, Dict[str, Any]], Any],
) -> None:
    buff_id = eff["buff_id"]
    stacks = int(eff.get("stacks", 1))
    target.add_buff(buff_id, stacks, source=ctx.caster)
    engine = getattr(ctx.caster, "engine", None)
    if engine and hasattr(engine, "log"):
        engine.log.append(f"{target.name} 获得了BUFF：{buff_id} ×{stacks}")


def op_dispel(
        eff: Dict[str, Any],
        ctx: Any,
        target: Any,
        scope: Dict[str, Any],
        eval_fn: Callable[[str, Dict[str, Any]], Any],
) -> None:
    count = int(eff.get("count", 1))
    positive = bool(eff.get("positive", True))
    target.dispel(count=count, positive=positive)
    engine = getattr(ctx.caster, "engine", None)
    if engine and hasattr(engine, "log"):
        t = "正面" if positive else "负面"
        engine.log.append(f"{target.name} 被驱散了{t}效果 ×{count}")


def op_damage_reduction(
        eff: Dict[str, Any],
        ctx: Any,
        target: Any,
        scope: Dict[str, Any],
        eval_fn: Callable[[str, Dict[str, Any]], Any],
) -> None:
    """伤害减免效果"""
    power_expr = eff.get("reduction", "0")
    reduction = float(eval_fn(power_expr, scope))
    # 这里需要修改伤害值，可以通过修改payload中的值来实现
    if 'actual_damage' in ctx.payload:
        reduced_damage = max(0, int(ctx.payload['actual_damage'] - reduction))
        ctx.payload['actual_damage'] = reduced_damage
    engine = getattr(ctx.caster, "engine", None)
    if engine and hasattr(engine, "log"):
        engine.log.append(f"{ctx.caster.name}减免了{reduction}点伤害")


def op_reflect_damage(
        eff: Dict[str, Any],
        ctx: Any,
        target: Any,
        scope: Dict[str, Any],
        eval_fn: Callable[[str, Dict[str, Any]], Any],
) -> None:
    """检查是否可以反伤"""
    if not ctx.payload.get("can_reflect"):
        return
    """反伤效果"""
    reflect_damage = int(eval_fn(eff.get("power"), scope))
    source = ctx.payload.get('source')
    damage_amount = ctx.payload.get('damage_amount', 0)

    if source and damage_amount > 0:
        # 直接对伤害来源造成伤害（不触发反伤循环）
        reflect_damage = source.take_damage(reflect_damage, source=target, can_reflect=False)

        engine = getattr(ctx.caster, "engine", None)
        if engine and hasattr(engine, "log"):
            engine.log.append(f"{target.name}触发了【{ctx.payload.get("skill_name")}】 反弹了 {reflect_damage} 点伤害给 {source.name}")


EFFECT_OPS = {
    "damage": op_damage,
    "damage_reduction": op_damage_reduction,
    "reflect_damage": op_reflect_damage,
    "heal": op_heal,
    "leech": op_leech,
    "stat_pct": op_stat_pct,
    "add_buff": op_add_buff,
    "dispel": op_dispel,
}
