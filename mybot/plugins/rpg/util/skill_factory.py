import random
from operator import truediv
from typing import Dict, Callable, List, Any

from mybot.plugins.rpg.engine.event_bus import EventBus
from .expression_evaluator import ExpressionEvaluator
from ..battle.entity import Entity


class SkillFactory:
    def __init__(self, config_loader, event_bus: EventBus):
        self.config_loader = config_loader
        self.event_bus = event_bus
        self.evaluator = ExpressionEvaluator()

    def create_skill(self, skill_id: str, owner) -> 'ConfigSkill':
        """从配置创建技能"""
        skill_config = self.config_loader.get_skill_config(skill_id)
        if not skill_config:
            raise ValueError(f"技能配置不存在: {skill_id}")

        return ConfigSkill(skill_config, owner, self.event_bus, self.evaluator)

    def create_buff(self, buff_id: str) -> 'Buff':
        """从配置创建Buff"""
        buff_config = self.config_loader.get_buff_config(buff_id)
        if not buff_config:
            raise ValueError(f"Buff配置不存在: {buff_id}")

        return Buff(
            buff_id,
            buff_config.get('name', buff_id),
            buff_config.get('duration', 1),
            buff_config.get('modifiers', {})
        )


class Buff:
    def __init__(self, buff_id: str, name: str, duration: int, modifiers: Dict[str, Any]):
        self.id = buff_id
        self.name = name
        self.duration = duration
        self.modifiers = modifiers

    def apply_effect(self, unit: Entity):
        """应用Buff效果"""
        # 在实际游戏中，这里会根据modifiers修改单位属性
        pass


class ConfigSkill:
    def __init__(self, config: Dict, owner, event_bus: EventBus, evaluator: ExpressionEvaluator):
        self.config = config
        self.id = config['id']
        self.name = config.get('name', self.id)
        self.type = config.get('type', 'passive')
        self.owner = owner
        self.event_bus = event_bus
        self.evaluator = evaluator
        self.current_cooldown = 0
        self.listeners = []

        self._register_triggers()

    def _register_triggers(self):
        """注册事件触发器"""
        triggers = self.config.get('triggers', [])
        for trigger_config in triggers:
            event_type = trigger_config.get('event_type')
            if event_type:
                handler = self._create_trigger_handler(trigger_config)
                priority = trigger_config.get('priority', 0)
                self.event_bus.subscribe(event_type, handler, priority)
                self.listeners.append((event_type, handler))

    def _create_trigger_handler(self, trigger_config: Dict) -> Callable:
        """创建触发处理器"""

        def handler(event_data):
            # 检查冷却和消耗
            if not self.can_activate():
                return None

            # 检查条件
            conditions = trigger_config.get('conditions', [])
            if not self._check_conditions(conditions, event_data,trigger_config.get("is_attacker")):
                return None

            # 激活技能
            self.activate(event_data)
            print(f"{self.owner.name} 施放技能{self.name}")

            # 是否停止事件传播
            return not trigger_config.get('stop_propagation', False)

        return handler

    def _check_conditions(self, conditions: List[Dict], event_data: Dict,attacker_check:bool) -> bool:
        """检查触发条件"""
        context = self._create_execution_context(event_data)

        # 攻击者检查
        if self.owner.name == event_data.get('source').name:
            is_attacker = True
        else:
            is_attacker = False
        if not(is_attacker  == attacker_check):
            return False
        if is_attacker and self.owner != event_data.get("source"):
            return False
        if not is_attacker and self.owner == event_data.get("source"):
            return False

        # 技能触发条件检查
        for condition in conditions:
            expr = condition.get('expr')
            if expr and not self.evaluator.evaluate(expr, context):
                return False

        return True

    def _create_execution_context(self, event_data: Dict = None) -> Dict:
        """创建用于效果执行的上下文（可修改原始数据）"""
        context = {
            'source': self.owner,
            'target': event_data.get('target'),
            'skill': self,
            'random': random.random
        }

        if event_data:
            context.update(event_data)

        return context

    def can_activate(self) -> bool:
        """检查技能是否可以激活"""
        if self.current_cooldown > 0:
            return False

        # 检查资源消耗
        cost = self.config.get('cost', {})
        for resource_type, amount in cost.items():
            current = getattr(self.owner, resource_type.upper(), 0)
            if current < amount:
                return False

        return True

    def activate(self, event_data: Dict = None):
        """激活技能"""
        context = self._create_execution_context(event_data)

        # 扣除消耗
        self._deduct_cost()

        # 设置冷却时间
        self.current_cooldown = self.config.get('cd', 0)

        # 执行效果
        effects = self.config.get('effects', [])
        self._execute_effects(effects, context)
        # 激活技能后，将context的内容反向更新到 event_data中
        event_data.update(context)

    def _deduct_cost(self):
        """扣除资源消耗"""
        cost = self.config.get('cost', {})
        for resource_type, amount in cost.items():
            current = getattr(self.owner, resource_type.upper(), 0)
            setattr(self.owner, resource_type.upper(), max(0, current - amount))

    def _execute_effects(self, effects: List[Dict], context: Dict):
        """执行技能效果"""
        for effect in effects:
            self._execute_single_effect(effect, context)

    def _execute_single_effect(self, effect: Dict, context: Dict):
        """执行单个效果"""
        op = effect.get('op')

        if op == 'deal_damage':
            self._execute_deal_damage(effect, context)
        elif op == 'heal':
            self._execute_heal(effect, context)
        elif op == 'damage_reduction':
            self._execute_damage_reduction(effect, context)
        elif op == 'apply_buff':
            self._execute_apply_buff(effect, context)
        elif op == 'apply_debuff':
            self._execute_apply_debuff(effect, context)
        elif op == 'modify_stat':
            self._execute_modify_stat(effect, context)

    def _execute_deal_damage(self, effect: Dict, context: Dict):
        """执行造成伤害效果"""
        formula = effect.get('formula', '0')
        damage_type = effect.get('damage_type', 'physical')
        target_ref = effect.get('target', 'target')

        damage = self.evaluator.evaluate(formula, context) or 0
        target = context.get(target_ref)

        if target and damage > 0:
            context['damage'] = damage

    def _execute_damage_reduction(self, effect: Dict, context: Dict):
        """执行伤害减免效果"""
        reduction_formula = effect.get('reduction', '0')
        reduction = self.evaluator.evaluate(reduction_formula, context) or 0

        if 'damage' in context:
            context['damage'] = max(0, context['damage'] - reduction)

    def _execute_heal(self, effect: Dict, context: Dict):
        """执行治疗效果"""
        formula = effect.get('formula', '0')
        target_ref = effect.get('target', 'target')

        heal_amount = self.evaluator.evaluate(formula, context) or 0
        target = context.get(target_ref)

        if target and heal_amount > 0:
            target.heal(heal_amount)

    def _execute_apply_buff(self, effect: Dict, context: Dict):
        """执行施加增益效果"""
        buff_id = effect.get('buff_id')
        duration = effect.get('duration', 1)
        target_ref = effect.get('target', 'target')

        target = context.get(target_ref)
        if target and buff_id:
            target.add_buff(buff_id, duration)

    def _execute_apply_debuff(self, effect: Dict, context: Dict):
        """执行施加减益效果"""
        debuff_id = effect.get('debuff_id')
        duration = effect.get('duration', 1)
        target_ref = effect.get('target', 'target')

        target = context.get(target_ref)
        if target and debuff_id:
            target.add_debuff(debuff_id, duration)

    def _execute_modify_stat(self, effect: Dict, context: Dict):
        """执行属性修改效果"""
        stat = effect.get('stat')
        value_formula = effect.get('value', '0')
        target_ref = effect.get('target', 'target')

        value = self.evaluator.evaluate(value_formula, context) or 0
        target = context.get(target_ref)

        if target and stat:
            current = getattr(target, stat, 0)
            setattr(target, stat, current + value)

    def update_cooldown(self):
        """更新冷却时间"""
        if self.current_cooldown > 0:
            self.current_cooldown -= 1

    def unregister_listeners(self):
        """取消注册所有监听器"""
        for event_type, handler in self.listeners:
            self.event_bus.unsubscribe(event_type, handler)
        self.listeners.clear()
