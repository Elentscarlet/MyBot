# 战斗事件
import uuid
from collections import defaultdict
from typing import Dict, Optional


class EventInfo:
    def __init__(self, source, target, round_num=0, is_crit=False, can_reflect=True, can_reduce=True,can_dodge =False, count_dict=None):
        # 行为发起者
        self.source = source
        # 行为目标
        self.target = target
        # 当前轮次
        self.round_num = round_num
        # 记录数值，一般为伤害，治疗量
        self.amount = 0
        # 记录数值，子事件（该事件触发的其他事件）
        self.amount_dict = defaultdict(int)
        # 记录数值，展示给日志
        self.last_amount = None
        # 当前操作
        self.op = None
        # 所用的技能
        self.skill_name = None
        # 是否暴击
        self.is_crit = is_crit
        # 是否被闪避
        self.is_dodged = False
        # 暂时无用 伤害类型
        self.damage_type = 'physical'
        # 是否可以反弹
        self.can_reflect = can_reflect
        # 是否可以被减免
        self.can_reduce = can_reduce
        # 是否可以被闪避
        self.can_dodge = can_dodge
        self.count_dict = count_dict if count_dict is not None else {}
        # 该事件下的子事件
        self.sub_event = []

        self.additional_msg =""

        # 事件关系追踪字段
        self.event_id = str(uuid.uuid4())
        self.parent_event_id: Optional[str] = None

    def todict(self):
        return {
            "source": self.source,
            "target": self.target,
        }

    def update(self, context: Dict):
        """
        根据上下文字典更新事件对象的属性。

        参数:
            context (Dict): 包含要更新的属性键值对的字典。
        """
        for key, value in context.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                # 如果上下文中有未知属性，可以选择忽略或引发异常
                # 这里我们选择忽略，但可以记录警告或根据需要处理
                pass

    def add_sub_event(self, event: 'EventInfo'):
        """添加子事件"""
        event.parent_event_id = self.event_id
        self.sub_event.append(event)