import random
import uuid
from dataclasses import dataclass, fields, field
from enum import Enum
from typing import Dict, List, Any


class BuffStackType(Enum):
    """Buff叠加类型"""
    NONE = 0  # 不可叠加
    DURATION = 1  # 刷新持续时间
    INTENSITY = 2  # 叠加层数
    BOTH = 3  # 同时叠加层数和持续时间


@dataclass
class Buff:
    # buff唯一标识
    id: str
    # 描述
    description: str

    # 属性变化
    property_change: dict
    # buff/debuff 区分
    is_positive: bool
    # 剩余时间
    duration: int
    # 叠加机制
    max_stack: int = 1
    current_stack: int = 1
    # 叠加类型
    stack_type: BuffStackType = BuffStackType.NONE

    # 条件表达式
    available_expr: List[str] = field(default_factory=list)

    # buff变化方式
    changes_on_turn_end: Dict[str, int] = field(default_factory=dict)

    # 来源
    source_id: str = None

    # 免疫和抵抗相关
    can_resist: bool = False  # 是否可被抵抗
    can_dispel: bool = True  # 是否可被驱散


def create_buff_from_dict(data: Dict[str, Any]) -> Buff:
    # 获取Buff类的所有字段名
    field_names = {f.name for f in fields(Buff)}

    # 处理 effects 列表，转换为 property_change 字典
    if 'effects' in data:
        property_change = {}
        for effect in data['effects']:
            if effect['op'] == 'property_change':
                stat = effect['stat']
                value = effect['value']
                property_change[stat] = value

        # 将 property_change 添加到数据中
        data['property_change'] = property_change
        # 移除 effects 字段，因为它不是 Buff 类的字段
        del data['effects']

    # 处理 stack_type 字符串转换为枚举
    if 'stack_type' in data and isinstance(data['stack_type'], str):
        data['stack_type'] = BuffStackType[data['stack_type']]

    # 只保留字典中与Buff字段匹配的键值对
    filtered_data = {k: v for k, v in data.items() if k in field_names}

    return Buff(**filtered_data)


class Entity:
    """战斗期实体：被技能引擎调用的唯一对象类型。"""

    def __init__(self, name: str, base_stats: Dict[str, int | float], tag: str = ""):
        self.id = uuid.uuid4()
        self.name = name
        self.tag = tag  # player/monster/boss等
        # 基础面板（不随战斗变化）
        self._ATK = base_stats["ATK"]
        self._DEF = base_stats["DEF"]
        self._AGI = base_stats["AGI"]
        self._CRIT = base_stats["CRIT"]
        self._MAX_HP = base_stats["MAX_HP"]
        self._HP = base_stats["MAX_HP"]

        # 战斗期可变状态
        self.is_alive = True
        self.skills: List[Any] = []
        self.buffs: List[Buff] = []
        # 技能引擎
        self.engine = None

    # 属性访问器
    @property
    def ATK(self) -> float:
        value = 0
        for buff in self.buffs:
            if "ATK" in buff.property_change and buff.property_change["ATK"]:
                value += buff.current_stack * buff.property_change["ATK"]
        return max(0, self._ATK + value)

    @ATK.setter
    def ATK(self, value):
        self._ATK = value

    @property
    def DEF(self) -> float:
        value = 0
        for buff in self.buffs:
            if "DEF" in buff.property_change and buff.property_change["DEF"]:
                value += buff.current_stack * buff.property_change["DEF"]
        # 防御可以被减成负数
        return self._DEF + value

    @DEF.setter
    def DEF(self, value):
        self._DEF = value

    @property
    def AGI(self) -> float:
        value = 0
        for buff in self.buffs:
            if "AGI" in buff.property_change and buff.property_change["AGI"]:
                value += buff.current_stack * buff.property_change["AGI"]
        return max(0, self._AGI + value)

    @AGI.setter
    def AGI(self, value):
        self._AGI = value

    @property
    def CRIT(self) -> float:
        value = 0
        for buff in self.buffs:
            if "CRIT" in buff.property_change and buff.property_change["CRIT"]:
                value += buff.current_stack * buff.property_change["CRIT"]
        return max(0, self._CRIT + value)

    @CRIT.setter
    def CRIT(self, value):
        self._CRIT = value

    @property
    def MAX_HP(self) -> float:
        value = 0
        for buff in self.buffs:
            if "MAX_HP" in buff.property_change and buff.property_change["MAX_HP"]:
                value += buff.current_stack * buff.property_change["MAX_HP"]
        return max(0, self._MAX_HP + value)

    @MAX_HP.setter
    def MAX_HP(self, value):
        self._MAX_HP = value

    @property
    def HP(self) -> float:
        value = 0
        for buff in self.buffs:
            if "HP" in buff.property_change and buff.property_change["HP"]:
                value += buff.current_stack * buff.property_change["HP"]
        return max(0, self._HP + value)

    @HP.setter
    def HP(self, value):
        self._HP = value

    # ===============适配新系统=============
    def take_damage(self, dmg_info: Dict[str, int]) -> float:
        """受到伤害"""
        if not self.is_alive:
            return 0

        # 计算实际伤害（考虑防御等）
        # 伤害减免率 = DEF / (DEF + 40) * 100%
        actual_damage = 0
        if self.DEF >= 0:
            damage_reduction = self.DEF / (self.DEF + 40)
        else:
            damage_reduction = self.DEF / 20
        for dmg_type, value in dmg_info.items():
            if dmg_type == "physical":
                actual_damage += max(0, int(value * (1 - damage_reduction)))
            else:
                actual_damage += value

        if actual_damage <= 0:
            actual_damage = 0

        self.HP = max(0, self.HP - actual_damage)

        # 检查死亡
        if self.HP <= 0:
            self.is_alive = False
            self.HP = 0

        return actual_damage

    def check_dodged(self) -> bool:
        min_dodge = 0.01  # 1% minimum chance
        max_dodge = 0.99  # 99% maximum chance

        prop = self.AGI / (self.AGI + 30)
        prop = max(min_dodge, min(max_dodge, prop))  # Clamp between min and max

        return random.random() < prop

    def heal(self, amount: float, can_apply_on_death: bool = False) -> float:
        """接受治疗"""
        if not self.is_alive and not can_apply_on_death:
            return 0

        actual_heal = min(amount, self.MAX_HP - self.HP)
        self.HP += actual_heal
        if self.HP > 0:
            self.is_alive = True

        return actual_heal

    def update_buffs(self):
        """更新Buff持续时间"""
        for buff in self.buffs:
            d = buff.property_change.get("duration", -1)
            buff.duration += d
            s = buff.property_change.get("stack", -1)
            buff.current_stack += s
            if buff.duration <= 0 or buff.current_stack <= 0:
                self.buffs.remove(buff)

    def update_skill_cooldowns(self):
        """更新技能冷却"""
        for skill in self.skills:
            if hasattr(skill, 'update_cooldown'):
                skill.update_cooldown()

    # ===== 临时加成 & Buff =====
    def add_buff(self, buff: Buff, source: str, stacks: int):
        buff.source_id = source
        buff.current_stack = min(buff.max_stack, stacks)

        for existing_buff in self.buffs:
            if existing_buff.id != buff.id:
                continue

            # 找到相同ID的buff，根据堆叠类型处理
            if existing_buff.stack_type == BuffStackType.DURATION:
                existing_buff.duration += buff.duration
            elif existing_buff.stack_type == BuffStackType.INTENSITY:
                existing_buff.current_stack = min(
                    existing_buff.max_stack,
                    existing_buff.current_stack + buff.current_stack
                )
            elif existing_buff.stack_type == BuffStackType.BOTH:
                existing_buff.duration += buff.duration
                existing_buff.current_stack = min(
                    existing_buff.max_stack,
                    existing_buff.current_stack + buff.current_stack
                )
            return existing_buff.current_stack # 无论哪种类型，处理完都返回

        # 如果没有找到相同ID的buff，则添加新buff
        self.buffs.append(buff)
        return buff.current_stack

    def remove_buff(self, buff_id: str, reason: str = ""):
        pass

    def dispel(self, count: int = 1, positive: bool = True):
        pass

    # ===== 生命周期 =====
    def is_alive(self) -> bool:
        return self.HP > 0
