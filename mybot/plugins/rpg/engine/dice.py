import random
import numpy as np


class DiceSimulator:
    def __init__(self):
        # 骰子面：0,0,1,1,2,2（其中一个2是特殊的）
        self.dice_faces = [0, 0, 1, 1, 2, 2]

        # 卡牌分布（与骰子一致）
        self.card_types = [0, 0, 1, 1, 2, 2]

    def simulate_single_trial(self, n_dice, n_cards, target_x):
        """
        单次模拟
        """
        total_score = 0
        zero_count = 0
        remaining_cards = self.card_types.copy()
        random.shuffle(remaining_cards)

        # 模拟投掷骰子
        for _ in range(n_dice):
            if zero_count >= 2:  # 已经有两个0，直接失败
                return False, total_score

            roll = random.choice(self.dice_faces)

            if roll == 0:
                zero_count += 1
                if zero_count >= 2:  # 投出第二个0，直接失败
                    return False, total_score
            else:
                total_score += roll

            # 检查是否是特殊2
            while roll == 2 and random.random() < 1 / 6:  # 1/6概率是特殊2
                # 获得额外投掷机会
                extra_roll = random.choice(self.dice_faces)
                roll = extra_roll
                total_score += extra_roll

        # 模拟抽卡
        for _ in range(min(n_cards, len(remaining_cards))):
            if len(remaining_cards) == 0:
                break

            card = remaining_cards.pop(0)
            if card == 0:
                zero_count += 1
                if zero_count >= 2:
                    return False, total_score
            total_score += card

            # 检查是否是特殊卡牌
            while card == 2 and random.random() < 1 / 6:  # 1/6概率是特殊卡
                # 获得额外投掷机会
                extra_roll = random.choice(self.dice_faces)
                card = extra_roll
                total_score += extra_roll

        # 检查是否成功
        success = total_score >= target_x and zero_count < 2
        return success, total_score

    def simulate_multiple_trials(self, n_dice, n_cards, target_x, num_trials=10000):
        """
        多次模拟计算概率
        """
        successes = 0
        failures = 0
        total_scores = []

        for _ in range(num_trials):
            success, score = self.simulate_single_trial(n_dice, n_cards, target_x)
            total_scores.append(score)

            if success:
                successes += 1
            else:
                failures += 1

        success_prob = successes / num_trials
        failure_prob = failures / num_trials

        # 统计信息
        avg_score = np.mean(total_scores)
        std_score = np.std(total_scores)
        min_score = min(total_scores)
        max_score = max(total_scores)

        return success_prob, failure_prob, avg_score, std_score, min_score, max_score

    def run_simulation(self, n_dice, n_cards, target_x, num_trials=10000) -> str:
        msg = ""
        """
        运行模拟程序
        """
        msg += "=== 骰子与卡牌模拟程序 ===\n"
        msg += "骰子面: [0, 0, 1, 1, 2, 2!]\n"
        msg += "卡牌分布: 与骰子一致\n"
        msg += "规则: 投出两个0直接失败，投出2!获得额外投掷机会\n"

        msg += f"\n开始模拟: {num_trials} 次试验..."

        success_prob, failure_prob, avg_score, std_score, min_score, max_score = self.simulate_multiple_trials(
            n_dice, n_cards, target_x, num_trials
        )

        msg += "\n=== 模拟结果 ==="
        msg += f"\n骰子数: {n_dice}"
        msg += f"\n抽卡数: {n_cards}"
        msg += f"\n目标值: {target_x}"
        msg += f"\n模拟次数: {num_trials}"
        msg += "\n---------------"
        msg += f"\n成功概率:  {success_prob * 100:.2f}%"
        msg += f"\n失败概率:  {failure_prob * 100:.2f}%"
        msg += "\n---------------"
        msg += f"\n平均得分: {avg_score:.2f}"
        msg += f"\n得分标准差: {std_score:.2f}"
        msg += f"\n最低得分: {min_score}"
        msg += f"\n最高得分: {max_score}"
        msg += "\n---------------"

        return msg
