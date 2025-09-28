from typing import Dict

from mybot.plugins.rpg.battle.entity import Buff
from mybot.plugins.rpg.battle.event_info import EventInfo
from mybot.plugins.rpg.util.expression_evaluator import ExpressionEvaluator
from mybot.plugins.rpg.util.skill_factory import _cal_crit_damage

def _create_execution_context(buff: Buff, event_data: EventInfo) -> Dict:
    """创建用于效果执行的上下文（可修改原始数据）"""
    context = {
        'source': event_data.source,
        'target': event_data.target,
        'current_stack': buff.current_stack,
        'owner': buff.source,
        'buff': buff.name
    }
    return context

def apply_buff_effect(buff: Buff, event_info: EventInfo):
    if not buff.effects:
        pass
    for effect in buff.effects:
        if effect.get("op") == "damage":
            _execute_damage(effect, _create_execution_context(buff, event_info), event_info)
        if effect.get("op") == "heal":
            _execute_heal(effect, _create_execution_context(buff, event_info), event_info)

def _execute_damage(effect: Dict, context: Dict, event_data: EventInfo):
    if effect.get("is_owner") is not None and effect.get("is_owner") == True:
        if context.get("owner") != context.get("source"):
            return
    elif effect.get("is_owner") is not None and effect.get("is_owner") == False:
        if context.get("owner") == context.get("source"):
            return

    """执行造成伤害效果"""
    formula = effect.get('formula', '0')
    damage_type = effect.get('damage_type', 'physical')
    evaluator = ExpressionEvaluator()
    damage = int(evaluator.evaluate(formula, context) or 0)
    if effect.get('can_crit'):
        damage = int(_cal_crit_damage(effect, context, damage))

    source = context.get('source')
    is_self_target = effect.get('is_self_target', False)
    if is_self_target:
        target = context.get('source')
    else :
        target = context.get('target')

    damage_event = EventInfo(source=source, target=target, round_num=effect.get('round_num'))
    damage_event.amount = damage
    damage_event.skill_name = context.get('buff')
    damage_event.damage_type = damage_type
    damage_event.op = effect.get('op')
    damage_event.can_dodge = effect.get('can_dodge', False)
    damage_event.is_crit = context.get('is_crit', False)

    event_data.add_sub_event(damage_event)

def _execute_heal(effect: Dict, context: Dict, event_data: EventInfo):
    if effect.get("is_owner") is not None and effect.get("is_owner") == True:
        if context.get("owner") != context.get("source"):
            return
    elif effect.get("is_owner") is not None and effect.get("is_owner") == False:
        if context.get("owner") == context.get("source"):
            return

    """执行造成伤害效果"""
    formula = effect.get('formula', '0')
    evaluator = ExpressionEvaluator()
    heal = int(evaluator.evaluate(formula, context) or 0)
    source = context.get('source')
    source.heal(heal, False)
    heal_event = EventInfo(source=source, target=source, round_num=effect.get('round_num'))
    heal_event.amount = heal
    heal_event.skill_name = context.get('buff')
    heal_event.op = effect.get('op')
    print(heal_event)

    event_data.add_sub_event(heal_event)
