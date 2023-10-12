from nonebot import require
from nonebot.typing import T_State
from nonebot.internal.matcher import Matcher
from nonebot.plugin import PluginMetadata, on_command

require("nonebot_plugin_saa")
from nonebot_plugin_saa import (  # noqa: E402
    SaaTarget,
    AggregatedMessageFactory,
    enable_auto_select_bot,
)

from .data_source import get_msg  # noqa: E402

__plugin_meta__ = PluginMetadata(
    name="GsCode",
    description="查询原神/星穹铁道前瞻直播兑换码",
    usage="""查询原神/星穹铁道前瞻直播兑换码
注意：经测试，兑换码接口返回与前瞻直播有 2 分钟左右延迟，应为正常现象，请耐心等待。
/gscode
/srcode""",
)

gs_code_matcher = on_command("gscode", aliases={"原神兑换码"}, priority=5)
sr_code_matcher = on_command("srcode", aliases={"铁道兑换码", "星穹铁道兑换码"}, priority=5)


@gs_code_matcher.handle()
@sr_code_matcher.handle()
async def _(target: SaaTarget, state: T_State, matcher: Matcher):
    if str(state["_prefix"]["command_arg"]):
        await matcher.finish()
    codes = await get_msg(
        target, "gs" if isinstance(matcher, gs_code_matcher) else "sr"
    )
    msg = AggregatedMessageFactory(list(codes))
    await msg.send_to(target)


enable_auto_select_bot()
