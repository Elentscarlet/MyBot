import pathlib

import yaml
import os
from typing import Dict, List, Any


class ConfigLoader:
    def __init__(self, config_path: str):
        self.config_path = pathlib.Path(__file__).resolve().parent.parent / "data"
        self.skills_config = self._load_config('skills.yaml')
        self.buffs_config = self._load_config('buffs.yaml')
        self.events_config = self._load_config('battle_event_type.yaml')

    def _load_config(self, filename: str) -> Dict[str, Any]:
        """加载YAML配置文件"""
        filepath = os.path.join(self.config_path, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or []
                return {item['id']: item for item in config}
        except FileNotFoundError:
            print(f"配置文件未找到: {filename}")
            return {}
        except Exception as e:
            print(f"加载配置文件错误 {filename}: {e}")
            return {}

    def get_skill_config(self, skill_id: str) -> Dict[str, Any]:
        """获取技能配置"""
        return self.skills_config.get(skill_id, {})

    def get_buff_config(self, buff_id: str) -> Dict[str, Any]:
        """获取Buff配置"""
        return self.buffs_config.get(buff_id, {})

    def get_all_skills(self) -> Dict[str, Dict]:
        """获取所有技能配置"""
        return self.skills_config

    def _build_event_limits(self):
        """构建事件次数限制映射"""
        self.event_limits = {}
        for event_config in self.events_config.values():
            event_type = event_config.get('event_type')
            max_count = event_config.get('max_count', 1)
            if event_type:
                self.event_limits[event_type] = max_count

    def get_event_limit(self, event_type: str) -> int:
        """获取事件类型的最大执行次数"""
        return self.event_limits.get(event_type, 1)  # 默认1次