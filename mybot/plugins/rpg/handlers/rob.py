import pathlib
import random
from typing import Dict, Any, Optional

import yaml
from nonebot.adapters.onebot.v11 import MessageEvent, Bot
from nonebot.plugin.on import on_keyword

from mybot.plugins.rpg.models import get_player, put_player
from mybot.plugins.rpg.penalty_manager import PenaltyManager
from mybot.plugins.rpg.utils import ids_of, first_at


# 加载配置文件
def load_rob_config():
    root = pathlib.Path(__file__).resolve().parent.parent  # .../rpg
    config_path = root / "data" / "rob_events.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


rob_config = load_rob_config()


class RobFailureManager:
    """抢夺失败事件管理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.failure_events = config["failure_events"]
        self.failure_penalties = config["failure_penalties"]
        self.event_weights = config["event_weights"]

    def get_random_failure_event(self) -> str:
        """根据权重获取随机失败事件"""
        # 根据权重选择事件类别
        categories = list(self.event_weights.keys())
        weights = list(self.event_weights.values())
        selected_category = random.choices(categories, weights=weights, k=1)[0]

        # 从选定的类别中随机选择事件
        events = self.failure_events[selected_category]
        return random.choice(events)

    def get_random_penalty(self) -> Optional[Dict[str, str]]:
        """根据概率获取随机惩罚"""
        probabilities = []

        for penalty in self.failure_penalties:
            probabilities.append(penalty["probability"])

        selected_penalty = random.choices(
            self.failure_penalties, weights=probabilities, k=1
        )[0]
        print(selected_penalty)
        return selected_penalty


failure_manager = RobFailureManager(rob_config)

# 初始化惩罚管理器
penalty_manager = PenaltyManager(rob_config)

rob = on_keyword({"抢夺"}, priority=10, block=True)


@rob.handle()
async def handle_rob(event: MessageEvent, bot: Bot):
    """处理抢夺命令"""
    gid = str(getattr(event, "group_id", 0))
    uid, gid, name = ids_of(event)

    # 获取被@的用户
    target = first_at(event)

    # 验证目标用户
    if not target:
        await rob.finish("请@一个目标用户！用法：抢夺 @某人")

    if target == uid:
        await rob.finish("不能抢夺自己哦！")

    print("start rob")
    # 检查惩罚限制
    can_rob, reason = penalty_manager.can_rob(uid, target)
    if not can_rob:
        await rob.finish(reason)

    # 加载双方玩家（OOP）
    a = get_player(uid, gid, name)
    info = await bot.get_group_member_info(group_id=int(gid), user_id=int(target))
    b = get_player(target, gid, info.get("card") or info.get("nickname") or target)

    # 模拟抢夺结果
    success = random.random() < rob_config["base_config"]["success_rate"]

    amount = random.randint(1, 200)
    if success:
        # 抢夺成功
        amount, _ = penalty_manager.apply_diamond_penalty(b, a, amount)
        result_message = (
            f"🎯 抢夺成功！\n"
            f"{name} 从 {b.name} 那里抢到了 {amount} 个💎！\n"
            f"当前钻石：{a.diamond}💎"
        )
    else:
        # 抢夺失败
        failure_event = failure_manager.get_random_failure_event()
        penalty_data = failure_manager.get_random_penalty()

        result_message = f"❌ 抢夺失败！\n" f"{name} {failure_event}"
        # 应用惩罚效果
        penalty_type = penalty_data["type"]
        effect = penalty_data["effect"]
        if penalty_type == "cooldown":
            # 时间惩罚
            duration = effect["duration"]
            penalty_text = penalty_manager.apply_time_penalty(uid, duration)
            result_message += f"\n{penalty_text}"
        elif penalty_type == "blacklist":
            # 黑名单惩罚
            duration = effect["duration"]
            penalty_text = penalty_manager.apply_blacklist_penalty(
                uid, target, duration
            )
            result_message += f"\n{penalty_text}"
        elif penalty_type == "diamond":
            _, penalty_text = penalty_manager.apply_diamond_penalty(a, b, amount)
            result_message += f"\n{penalty_text}"
        else:
            # 其他惩罚
            result_message += f"\n{penalty_data['penalty']}"

        result_message += "\n⚠️ 下次小心点哦～"
    put_player(a)
    put_player(b)
    await rob.finish(result_message)
