import json
import time
from pathlib import Path
from typing import Dict, Any

from mybot.plugins.rpg.models import Player


class PenaltyManager:
    """惩罚管理系统"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.user_cooldowns: Dict[str, Dict[str, float]] = {}  # 用户冷却时间
        self.user_blacklists: Dict[str, Dict[str, float]] = {}  # 用户黑名单
        self.user_stats: Dict[str, Dict[str, Any]] = {}  # 用户统计
        self.data_file = Path("data/rob_penalties.json")
        self.load_data()

    def load_data(self):
        """加载持久化数据"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_cooldowns = data.get('cooldowns', {})
                    self.user_blacklists = data.get('blacklists', {})
                    self.user_stats = data.get('stats', {})
        except Exception as e:
            print(f"加载惩罚数据失败: {e}")

    def save_data(self):
        """保存数据到文件"""
        try:
            self.data_file.parent.mkdir(exist_ok=True)
            data = {
                'cooldowns': self.user_cooldowns,
                'blacklists': self.user_blacklists,
                'stats': self.user_stats
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存惩罚数据失败: {e}")

    def apply_time_penalty(self, user_id: str, duration: int) -> str:
        """应用时间惩罚"""
        current_time = time.time()
        current_cooldown = self.get_remaining_cooldown(user_id)

        # 计算新的冷却时间
        new_cooldown = max(current_cooldown, duration)

        end_time = current_time + new_cooldown
        self.user_cooldowns[user_id] = {'end_time': end_time, 'penalty_type': 'time'}

        self.save_data()
        return f"冷却时间增加至 {self.format_duration(new_cooldown)}"

    def apply_blacklist_penalty(self, user_id: str, target_id: str, duration: int) -> str:
        """应用黑名单惩罚"""
        current_time = time.time()
        end_time = current_time + duration

        if user_id not in self.user_blacklists:
            self.user_blacklists[user_id] = {}

        self.user_blacklists[user_id][target_id] = end_time
        self.save_data()
        return f"24小时内无法抢夺该玩家"

    def apply_diamond_penalty(self, p1: Player, p2: Player, amount: int):
        if p1.diamond < amount:
            amount = p1.diamond
        p1.diamond -= amount
        p2.diamond += amount
        self.save_data()
        return amount, f"损失{amount}个钻石💎"

    def get_remaining_cooldown(self, user_id: str) -> int:
        """获取剩余冷却时间"""
        if user_id in self.user_cooldowns:
            end_time = self.user_cooldowns[user_id]['end_time']
            remaining = max(0, end_time - time.time())
            return int(remaining)
        return 0

    def is_user_blacklisted(self, user_id: str, target_id: str) -> bool:
        """检查用户是否被目标用户黑名单"""
        if user_id in self.user_blacklists and target_id in self.user_blacklists[user_id]:
            end_time = self.user_blacklists[user_id][target_id]
            return time.time() < end_time
        return False

    def can_rob(self, user_id: str, target_id: str) -> tuple[bool, str]:
        """检查是否可以抢夺"""
        # 检查冷却时间
        cooldown = self.get_remaining_cooldown(user_id)
        if cooldown > 0:
            return False, f"⏰ 冷却中！请等待 {self.format_duration(cooldown)}"

        # 检查黑名单
        if self.is_user_blacklisted(user_id, target_id):
            blacklist_end = self.user_blacklists[user_id][target_id]
            remaining = max(0, blacklist_end - time.time())
            return False, f"🚫 被目标玩家拉黑！请等待 {self.format_duration(remaining)}"

        return True, ""

    def format_duration(self, seconds: int) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分钟"
        else:
            return f"{seconds // 3600}小时{(seconds % 3600) // 60}分钟"

    def cleanup_expired_penalties(self):
        """清理过期的惩罚"""
        current_time = time.time()

        # 清理过期冷却时间
        expired_users = []
        for user_id, data in self.user_cooldowns.items():
            if data['end_time'] <= current_time:
                expired_users.append(user_id)

        for user_id in expired_users:
            del self.user_cooldowns[user_id]

        # 清理过期黑名单
        for user_id in list(self.user_blacklists.keys()):
            expired_targets = []
            for target_id, end_time in self.user_blacklists[user_id].items():
                if end_time <= current_time:
                    expired_targets.append(target_id)

            for target_id in expired_targets:
                del self.user_blacklists[user_id][target_id]

            if not self.user_blacklists[user_id]:
                del self.user_blacklists[user_id]

        self.save_data()

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户统计信息"""
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                'total_attempts': 0,
                'success_count': 0,
                'failure_count': 0,
                'total_cooldown': 0,
                'blacklist_count': 0
            }
        return self.user_stats[user_id]

    def update_user_stats(self, user_id: str, success: bool, cooldown: int = 0):
        """更新用户统计"""
        stats = self.get_user_stats(user_id)
        stats['total_attempts'] += 1

        if success:
            stats['success_count'] += 1
        else:
            stats['failure_count'] += 1
            stats['total_cooldown'] += cooldown

        self.save_data()
