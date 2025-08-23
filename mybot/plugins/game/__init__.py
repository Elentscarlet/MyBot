from nonebot import get_plugin_config
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me, keyword
from nonebot.plugin import on_command
from nonebot.plugin import on_keyword
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="Game",
    description="",
    usage="",
    config=Config,
)

weather = on_command("天气", rule=to_me(), aliases={"weather", "查天气"}, priority=10, block=True)
@weather.handle()
async def handle_function():
    # await weather.send("天气是...")
    await weather.finish("天气是...")

no_cmd = on_keyword({"wym"}, priority=10, block=True)
@no_cmd.handle()
async def handle_function():
    await no_cmd.finish("谁是wym")

echo_group = on_command("test",rule=keyword("123"),priority=10,block=True)
@echo_group.handle()
async def handle_group_message(event: GroupMessageEvent):
    # 获取消息内容
    message = event.get_plaintext().strip()

    await echo_group.send(f"你好，{event.sender.nickname}!,我叫wym!")

    await echo_group.finish(message)

config = get_plugin_config(Config)

