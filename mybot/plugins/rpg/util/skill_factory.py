import random
from typing import Dict, Callable, List

from .expression_evaluator import ExpressionEvaluator
from ..battle.entity import Buff, create_buff_from_dict
from ..battle.event_info import EventInfo
from ..engine.event_bus import EventBus


class SkillFactory:
    def __init__(self, config_loader, event_bus: EventBus):
        self.config_loader = config_loader
        self.event_bus = event_bus
        self.evaluator = ExpressionEvaluator()

    def create_skill(self, skill_id: str, owner, level: int = None) -> 'ConfigSkill':
        """从配置创建技能"""
        skill_config = self.config_loader.get_skill_config(skill_id)
        if not skill_config:
            raise ValueError(f"技能配置不存在: {skill_id}")

        return ConfigSkill(skill_config, owner, self.event_bus, self.evaluator, level, self.config_loader)


class ConfigSkill:
    def __init__(self, config: Dict, owner, event_bus: EventBus, evaluator: ExpressionEvaluator, level, config_loader):
        self.config_loader = config_loader
        self.config = config
        self.id = config['id']
        self.name = config.get('name', self.id)
        self.type = config.get('type', 'passive')
        self.level = level if level else config.get('level', 1)
        self.owner = owner
        self.event_bus = event_bus
        self.evaluator = evaluator
        self.current_cooldown = 0
        self.listeners = []

        self._register_triggers()
        self.op_handlers = {
            'damage': self._execute_damage,
            'damage_reduction': self._execute_damage_reduction,
            'add_damage': self._execute_add_damage,
            'reflect_damage': self._execute_damage_reflect,
            'heal': self._execute_heal,
            'apply_buff': self._execute_apply_buff,
            'leech': self._execute_leech
        }

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
            if not self._check_conditions(conditions, event_data, trigger_config.get("is_attacker")):
                return None

            # 激活技能
            self.activate(event_data)

            return True

        return handler

    def _check_conditions(self, conditions: List[Dict], event_data: EventInfo, attacker_check: bool) -> bool:
        """检查触发条件"""
        context = self._create_execution_context(event_data)
        # 自己不触发自己
        if self == event_data.skill:
            return False
        # 攻击者检查
        if self.owner.name == event_data.source.name:
            is_attacker = True
        else:
            is_attacker = False
        if not (is_attacker == attacker_check):
            return False
        if is_attacker and (self.owner != event_data.source or self.owner == event_data.target):
            return False
        if not is_attacker and (self.owner == event_data.source or self.owner != event_data.target):
            return False

        # 技能触发条件检查
        for condition in conditions:
            expr = condition.get('expr')
            if expr and not self.evaluator.evaluate(expr, context):
                return False

        return True

    def _create_execution_context(self, event_data: EventInfo) -> Dict:
        """创建用于效果执行的上下文（可修改原始数据）"""
        context = {
            'source': self.owner,
            'target': event_data.target,
            'skill': self,
            'damage_type': event_data.damage_type,
            'damage': event_data.last_amount if event_data.last_amount is not None else event_data.amount,
            'amount': event_data.amount,
            'op_type': event_data.op,
            'is_crit': event_data.is_crit,
            'is_dodged': event_data.is_dodged,
        }

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

    def activate(self, event_data: EventInfo = None):
        """激活技能"""
        context = self._create_execution_context(event_data)

        # 扣除消耗
        self._deduct_cost()

        # 设置冷却时间
        self.current_cooldown = self.config.get('cd', 0)

        # 执行效果
        effects = self.config.get('effects', [])
        self._execute_effects(effects, context, event_data)

    def _deduct_cost(self):
        """扣除资源消耗"""
        cost = self.config.get('cost', {})
        for resource_type, amount in cost.items():
            current = getattr(self.owner, resource_type.upper(), 0)
            setattr(self.owner, resource_type.upper(), max(0, current - amount))

    def _execute_effects(self, effects: List[Dict], context: Dict, event_data: EventInfo):
        """执行技能效果"""
        for effect in effects:
            self._execute_single_effect(effect, context, event_data)

    def _execute_single_effect(self, effect: Dict, context: Dict, event_data: EventInfo):
        """执行单个效果"""
        op = effect.get('op')
        # 操作类型到处理方法的映射

        # 获取对应的处理方法
        handler = self.op_handlers.get(op)

        if handler:
            # 根据操作类型调用相应的方法
            return handler(effect, context, event_data)
        return None

    def _execute_damage(self, effect: Dict, context: Dict, event_data: EventInfo):
        """执行造成伤害效果"""
        formula = effect.get('formula', '0')
        damage_type = effect.get('damage_type', 'physical')

        damage = int(self.evaluator.evaluate(formula, context) or 0)
        if effect.get('can_crit'):
            damage = int(self._cal_crit_damage(effect, context, damage))
        target = context.get('target')
        damage_event = EventInfo(source=self.owner, target=target, round_num=effect.get('round_num'))
        damage_event.skill = self
        damage_event.amount = damage
        damage_event.damage_type = damage_type
        damage_event.op = effect.get('op')
        damage_event.can_dodge = effect.get('can_dodge', False)
        damage_event.is_crit = context.get('is_crit', False)

        event_data.add_sub_event(damage_event)

    def _execute_damage_reduction(self, effect: Dict, context: Dict, event_data: EventInfo):
        """执行伤害减免效果"""
        if not event_data.can_reduce:
            self.current_cooldown = 0
            return False

        reduction_formula = effect.get('formula', '0')
        reduction = int(max(self.evaluator.evaluate(reduction_formula, context) or 0), 0)

        reduction_event = EventInfo(source=self.owner, target=event_data.target, round_num=event_data.round_num,
                                    can_reflect=False, can_dodge=False)
        reduction_event.skill = self
        reduction_event.amount = reduction
        reduction_event.op = effect.get('op')
        reduction_event.can_reflect = False
        reduction_event.damage_type = effect.get('damage_type', 'physical')
        event_data.amount_dict['reduction'] -= reduction
        event_data.add_sub_event(reduction_event)
        return True

    def _execute_add_damage(self, effect: Dict, context: Dict, event_data: EventInfo):
        """执行伤害增加效果"""
        dmg_formula = effect.get('formula', '0')
        dmg = int(self.evaluator.evaluate(dmg_formula, context) or 0)
        dmg_event = EventInfo(source=self.owner, target=event_data.target, round_num=event_data.round_num,
                              can_reflect=False, can_dodge=False)
        dmg_event.skill = self
        dmg_event.amount = dmg
        dmg_event.op = effect.get('op')
        dmg_event.damage_type = effect.get('damage_type', 'physical')
        event_data.amount_dict['fire'] += dmg

        event_data.add_sub_event(dmg_event)
        return True

    def _execute_damage_reflect(self, effect: Dict, context: Dict, event_data: EventInfo):
        if not event_data.can_reflect:
            self.current_cooldown = 0
            return False
        """执行伤害反射效果"""
        reflect_formula = effect.get('formula', '0')
        reflect_type = effect.get('damage_type', 'physical')
        reflect_target = event_data.source  # 默认反射给伤害来源

        # 计算反射伤害
        reflect_damage = int(self.evaluator.evaluate(reflect_formula, context) or 0)
        reflect_event = EventInfo(source=self.owner, target=reflect_target, round_num=event_data.round_num,
                                  can_reflect=False, can_dodge=False)
        reflect_event.skill = self
        reflect_event.amount = reflect_damage
        reflect_event.damage_type = reflect_type
        reflect_event.op = effect.get('op')
        event_data.add_sub_event(reflect_event)
        return True

    def _execute_leech(self, effect: Dict, context: Dict, event_data: EventInfo):
        if event_data.is_dodged:
            self.current_cooldown = 0
            return False
        """执行吸血效果"""
        leech_formula = effect.get('formula', '0')
        leech_target = context.get('source')  # 默认吸血给施法者

        # 计算吸血量
        leech_amount = int(self.evaluator.evaluate(leech_formula, context) or 0)
        if leech_amount > 0:
            leech_amount = leech_target.heal(leech_amount)

        leech_event = EventInfo(source=self.owner, target=event_data.target, round_num=event_data.round_num,
                                can_reflect=False)
        leech_event.skill = self
        leech_event.amount = leech_amount
        leech_event.op = effect.get('op')
        event_data.add_sub_event(leech_event)

    def _cal_crit_damage(self, effect: Dict, context: Dict, dmg) -> float:
        source = context.get('source')
        crit_stat = source.CRIT  # 暴击属性 (0~1)
        # 暴击倍率，目前最大爆伤 = 最小爆伤+1
        min_crit_multiplier = effect.get('crit_multiplier', 1.0)
        max_crit_multiplier = effect.get('crit_multiplier', 1.0) + 1.0
        if random.random() < crit_stat:
            context["is_crit"] = True
            crit_multiplier = min_crit_multiplier + source.CRIT * (max_crit_multiplier - min_crit_multiplier)
            return dmg * crit_multiplier
        context["is_crit"] = False
        return dmg

    def _execute_heal(self, effect: Dict, context: Dict, event_data: EventInfo):
        """执行治疗效果"""
        formula = effect.get('formula', '0')
        target_ref = effect.get('target', 'target')
        can_apply_on_death = effect.get('can_apply_on_death', False)

        heal_amount = int(self.evaluator.evaluate(formula, context) or 0)
        target = context.get(target_ref)

        if target and heal_amount > 0:
            target.heal(heal_amount, can_apply_on_death)

        heal_event = EventInfo(source=self.owner, target=event_data.target, round_num=event_data.round_num,
                               can_reflect=False)
        heal_event.skill = self
        heal_event.amount = heal_amount
        heal_event.last_amount = heal_amount
        heal_event.op = effect.get('op')
        event_data.add_sub_event(heal_event)

    def _execute_apply_buff(self, effect: Dict, context: Dict, event_data: EventInfo):
        """执行施加增益/减益效果"""
        stacks_formula = effect.get('stacks_formula', '1')
        is_self_target = effect.get('is_self_target', False)
        stacks = int(self.evaluator.evaluate(stacks_formula, context) or 0)
        buff_config = self.config_loader.get_buff_config(effect.get('buff_id'))
        buff = create_buff_from_dict(buff_config)
        if is_self_target:
            target = event_data.source
        else:
            target = event_data.target

        stack = target.add_buff(buff, event_data.source.id, stacks)

        buff_event = EventInfo(source=self.owner, target=target,can_dodge=False,can_reflect=False,can_reduce=False)
        buff_event.skill = self
        buff_event.op = effect.get('op')
        buff_event.additional_msg = buff.description + f"(累计{stack}层)"
        event_data.add_sub_event(buff_event)

    def update_cooldown(self):
        """更新冷却时间"""
        if self.current_cooldown > 0:
            self.current_cooldown -= 1

    def unregister_listeners(self):
        """取消注册所有监听器"""
        for event_type, handler in self.listeners:
            self.event_bus.unsubscribe(event_type, handler)
        self.listeners.clear()
