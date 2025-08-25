import os
import sys

from mybot.plugins.rpg.battle.adapters import player_to_entity
from mybot.plugins.rpg.engine.battle_system import BattleSystem
from mybot.plugins.rpg.engine.skill_engine import SkillEngine
from mybot.plugins.rpg.logic_skill import equip_skills_for_player
from mybot.plugins.rpg.models import Player, Weapon
from mybot.plugins.rpg.util.config_loader import ConfigLoader
from mybot.plugins.rpg.util.skill_factory import SkillFactory

sys.path.append(os.path.dirname(os.path.abspath(__file__)))



def main():
    # 初始化系统
    config_loader = ConfigLoader('./config/')
    battle_system = BattleSystem()
    skill_factory = SkillFactory(config_loader, battle_system.event_bus)

    # 创建战斗单位
    p1 = Player(uid="1", gid="1", name="Wym")
    p2 = Player(uid="2", gid="1", name="Bob")
    # 给玩家分配基础属性和武器
    p1.points.str = 55
    p1.points.hp = 1
    p1.points.def_ = 90
    p1.weapon = Weapon(name="测试剑", slots=[1, 1, 1])
    p2.points.str = 10
    p2.points.hp = 1
    p2.points.def_ = 1
    p2.weapon = Weapon(name="测试斧", slots=[1, 1, 1])

    ent_a = player_to_entity(p1)
    ent_b = player_to_entity(p2)

    # 注入引擎
    eng = SkillEngine(seed=1)
    ent_a.engine = eng
    ent_b.engine = eng


    equip_skills_for_player(p1, ent_a,skill_factory)
    equip_skills_for_player(p2, ent_b,skill_factory)

    # 添加到战斗系统
    battle_system.add_unit(ent_a)
    battle_system.add_unit(ent_b)

    max_turns =6
    # 开始战斗
    battle_system.start_battle()
    print("\n=== 战斗模拟开始 ===")
    for turn in range(1, max_turns + 1):
        battle_system.start_round()
        print(f"玩家生命: {ent_a.HP}, 怪物生命: {ent_b.HP}")
        battle_system.process_attack(ent_a, ent_b, )
        print(f"玩家生命: {ent_a.HP}, 怪物生命: {ent_b.HP}")
        battle_system.end_round()


if __name__ == "__main__":
    main()