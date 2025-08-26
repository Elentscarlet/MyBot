import time
from typing import Dict, List, Optional, Any

from mybot.plugins.rpg.battle.event_info import EventInfo


class EventChainTracker:
    """事件链追踪器"""

    def __init__(self):
        self.event_chains: Dict[str, Dict[str, Any]] = {}  # 存储所有事件链
        self.current_chain_id: Optional[str] = None  # 当前事件链ID
        self.all_events: Dict[str, EventInfo] = {}  # 所有事件的映射表

    def start_new_chain(self, initial_event: EventInfo) -> str:
        """开始新的事件链"""
        chain_id = initial_event.event_id
        self.event_chains[chain_id] = {
            'root_event': initial_event,
            'events': [initial_event],
            'structure': {},  # 事件树结构 {parent_id: [child_id1, child_id2, ...]}
            'start_time': time.time(),
            'end_time': None,
            'round_num': initial_event.round_num
        }
        self.current_chain_id = chain_id
        self.all_events[initial_event.event_id] = initial_event
        return chain_id

    def add_event_to_chain(self, event: EventInfo, parent_event_id: Optional[str] = None) -> None:
        """添加事件到当前事件链"""
        if self.current_chain_id and self.current_chain_id in self.event_chains:
            chain = self.event_chains[self.current_chain_id]

            # 添加到事件列表
            if event.event_id not in [e.event_id for e in chain['events']]:
                chain['events'].append(event)
                self.all_events[event.event_id] = event

            # 记录事件关系
            if parent_event_id:
                if parent_event_id not in chain['structure']:
                    chain['structure'][parent_event_id] = []
                if event.event_id not in chain['structure'][parent_event_id]:
                    chain['structure'][parent_event_id].append(event.event_id)

    def end_current_chain(self) -> None:
        """结束当前事件链"""
        if self.current_chain_id and self.current_chain_id in self.event_chains:
            self.event_chains[self.current_chain_id]['end_time'] = time.time()
            self.current_chain_id = None

    def get_event_chain(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """获取指定事件链"""
        return self.event_chains.get(chain_id)

    def get_event_by_id(self, event_id: str) -> Optional[EventInfo]:
        """根据ID获取事件"""
        return self.all_events.get(event_id)

    def get_chain_events(self, chain_id: str) -> List[EventInfo]:
        """获取事件链中的所有事件"""
        chain = self.get_event_chain(chain_id)
        return chain['events'] if chain else []

    def get_event_children(self, event_id: str) -> List[EventInfo]:
        """获取事件的所有子事件"""
        children = []
        if self.current_chain_id and self.current_chain_id in self.event_chains:
            chain = self.event_chains[self.current_chain_id]
            if event_id in chain['structure']:
                for child_id in chain['structure'][event_id]:
                    child_event = self.get_event_by_id(child_id)
                    if child_event:
                        children.append(child_event)
        return children