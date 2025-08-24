import random

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.plugin.on import on_fullmatch

from mybot.plugins.rpg.logic_battle import simulate_pvp_with_skills
from mybot.plugins.rpg.logic_economy import get_fish, get_counter
from mybot.plugins.rpg.models import get_player, put_player, Player
from mybot.plugins.rpg.storage import load_players
from mybot.plugins.rpg.utils import ids_of

cmd_fishing = on_fullmatch("钓鱼")


@cmd_fishing.handle()
async def _(event: MessageEvent):
    uid, gid, name = ids_of(event)
    p = get_player(uid, gid, name)
    if p.diamond < 10:
        await cmd_fishing.finish(f"就这么点钻石还想钓鱼？ 剩余钻石:{p.diamond}💎")
    fish_result = ""
    fish_result += "花费10钻石开始钓鱼！\n"
    fish_result += "♪～(￣、￣ )ﾉ 彡🎣\n"
    fish_result += "(　´-｀)ﾉｼ🎣\n"
    fish_result += "∠( ᐛ 」∠)＿ ～～～🐟\n"
    fish_result += "(￣￣￣￣￣￣￣￣￣)ｼﾞｰｯ🎣\n"
    p.diamond -= 10
    r = random.random()
    if r < 0.7:
        fish_get, pool_msg = get_fish(gid)
        if fish_get:
            size = random.randint(fish_get['min_size'], fish_get['max_size'])
            p.diamond += size
            fish_result += f"🎉 哇！鱼竿猛地一沉！你钓到了一条{fish_get['name']}！\n"
            fish_result += f"📏 尺寸：{size}厘米 | 💎 价值：{size}钻石\n"

            # 根据鱼的大小添加不同的反应
            if size > 100:
                fish_result += "🌟 这绝对是今日最佳收获！周围的钓鱼佬都投来了羡慕的目光！\n"
            elif size > 30:
                fish_result += "👍 不错的收获！这条鱼挣扎得很厉害呢！\n"
            else:
                fish_result += "🐟 虽然不大，但也是不错的开始！\n"
            fish_result += pool_msg + '\n'
        else:
            fish_result += f"…(｡•́︿•̀｡)… 没有钓到鱼…\n"
            fish_result += pool_msg + '\n'
    elif r < 0.9:
        # todo 这里进入战斗
        # 遭遇敌人
        enemy = "【王一梅】"
        fish_result += f"⚔️ 突然！{enemy}从水中跃出，向你发起了攻击！\n"
        fish_result += f"经过一番搏斗，你成功击退了{enemy}，并获得了{enemy}的宝藏！\n"
        fish_result += f"💎 获得战利品：10钻石\n"
        p.diamond += 10
    else:
        data = load_players()
        player_in_same_group = []
        for player_key, player_data in data.items():
            if player_data['gid'] == gid and player_data['uid'] != uid:
                player_in_same_group.append(player_data)
        # 如果为空跳过
        if not player_in_same_group:
            fish_result += "风平浪静，无事发生。你既没有钓到鱼，也没有遇到任何奇遇。"
            put_player(p)
            fish_result += f"结算数据：剩余钻石:{p.diamond}💎"
            await cmd_fishing.finish(fish_result)
            return

        player_to_battle = Player.from_dict(random.choice(player_in_same_group))
        result, logs = simulate_pvp_with_skills(p, player_to_battle)
        fish_result += f"遭遇：{player_to_battle.name}！\n眼神对视，战斗无法避免！\n"
        for log in logs:
            fish_result += log + '\n'
        diamond_change = random.randint(10, 100)
        if result == "win":
            if diamond_change > player_to_battle.diamond:
                diamond_change = player_to_battle.diamond
            p.diamond += diamond_change
            player_to_battle.diamond -= diamond_change
            put_player(player_to_battle)
            fish_result += f"战斗胜利！成功从{player_to_battle.name}手中夺得了{diamond_change}颗钻石！✨"
        elif result == "lose":
            if diamond_change > p.diamond:
                diamond_change = p.diamond
            p.diamond -= diamond_change
            player_to_battle.diamond += diamond_change
            put_player(player_to_battle)
            fish_result += f"战斗失利……{player_to_battle.name}从你这里夺走了{diamond_change}颗钻石💎"
        elif result == "draw":
            pass
    put_player(p)
    fish_result += f"结算数据：剩余钻石:{p.diamond}💎"
    await cmd_fishing.finish(fish_result)
