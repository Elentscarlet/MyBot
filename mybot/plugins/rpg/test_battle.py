import os
import sys

from mybot.plugins.rpg.logic_battle import simulate_pvp_with_skills
from mybot.plugins.rpg.models import Player, Weapon

sys.path.append(os.path.dirname(os.path.abspath(__file__)))



def main():

    # 创建战斗单位
    p1 = Player(uid="1", gid="1", name="A")
    p2 = Player(uid="2", gid="1", name="B")
    # 给玩家分配基础属性和武器
    p1.points.str = 7
    p1.points.hp = 1
    p1.points.def_ = 0
    p1.points.agi = 4
    p1.points.crit = 7
    p1.config.battle_report_model = 0
    p1.weapon = Weapon(name="测试剑", slots=[1, 1, 1])
    p2.points.str = 2
    p2.points.hp = 20
    p2.points.def_ = 0
    p2.points.agi = 3
    p2.points.crit = 0
    p2.weapon = Weapon(name="测试斧", slots=[1, 1, 1])

    result, logs = simulate_pvp_with_skills(p1, p2,99,0)
    print("\n".join(logs))


if __name__ == "__main__":
    main()