import json
from datetime import datetime, timedelta, timezone
from re import findall, sub
from time import time
from typing import Dict, List, Union

from httpx import AsyncClient
from nonebot.log import logger
from nonebot_plugin_saa import (
    AggregatedMessageFactory,
    MessageFactory,
    PlatformTarget,
    Text,
)

Sendable = Union[MessageFactory, AggregatedMessageFactory]
TZ = timezone(timedelta(hours=8))


async def get_data(type, mhy_type: str = "", data: Dict = {}) -> Dict:
    """米哈游接口请求"""

    uid = 288909600 if mhy_type == "sr" else 75276550
    url = {
        "act_id": f"https://bbs-api.mihoyo.com/painter/api"
        f"/user_instant/list?offset=0&size=20&uid={uid}",
        "index": "https://api-takumi.mihoyo.com/event/miyolive/index",
        "code": "https://api-takumi-static.mihoyo.com/event/miyolive/refreshCode",
    }
    async with AsyncClient() as client:
        try:
            if type == "index":
                res = await client.get(
                    url[type], headers={"x-rpc-act_id": data.get("actId", "")}
                )
            elif type == "code":
                res = await client.get(
                    url[type],
                    params={
                        "version": data.get("version", ""),
                        "time": f"{int(time())}",
                    },
                    headers={"x-rpc-act_id": data.get("actId", "")},
                )
            else:
                res = await client.get(url[type])
            return res.json()
        except Exception as e:
            logger.opt(exception=e).error(f"{type} 接口请求错误")
            return {"error": f"[{e.__class__.__name__}] {type} 接口请求错误"}


async def get_act_id(mhy_type) -> str:
    """获取 ``act_id``"""

    ret = await get_data(type="act_id", mhy_type=mhy_type)
    if ret.get("error") or ret.get("retcode") != 0:
        return ""

    act_id = ""
    keywords = ["版本前瞻特别节目"]
    for p in ret["data"]["list"]:
        post = p.get("post", {}).get("post", {})
        if not post:
            continue
        if not all(word in post["subject"] for word in keywords):
            continue
        shit = json.loads(post["structured_content"])
        for segment in shit:
            link = segment.get("attributes", {}).get("link", "")
            if "直播" in segment.get("insert", "") and link:
                matched = findall(r"act_id=(.*?)\&", link)
                if matched:
                    act_id = matched[0]
        if act_id:
            break

    return act_id


async def get_live_data(act_id: str) -> Dict:
    """获取直播数据，尤其是 ``code_ver``"""

    ret = await get_data(type="index", data={"actId": act_id})
    if ret.get("error") or ret.get("retcode") != 0:
        return {"error": ret.get("error") or "前瞻直播数据异常"}

    live_data_raw = ret["data"]["live"]
    live_template = json.loads(ret["data"]["template"])
    live_data = {
        "code_ver": live_data_raw["code_ver"],
        "title": live_data_raw["title"].replace("特别节目", ""),
        "header": live_template["kvDesktop"],
        "room": live_template["liveConfig"][0]["desktop"],
    }
    if live_data_raw["is_end"]:
        review_url = live_template["reviewUrl"]
        live_data["review"] = (
            review_url
            if isinstance(review_url, str)
            else review_url["args"].get("post_id")
        )
    else:
        now = datetime.fromtimestamp(time(), TZ)
        start = datetime.strptime(live_data_raw["start"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=TZ
        )
        if now < start:
            live_data["start"] = live_data_raw["start"]

    return live_data


async def get_codes(version: str, act_id: str) -> Union[Dict, List[Dict]]:
    """获取兑换码"""

    ret = await get_data(type="code", data={"version": version, "actId": act_id})
    if ret.get("error") or ret.get("retcode") != 0:
        return {"error": ret.get("error") or "兑换码数据异常"}

    codes_data = []
    for code_info in ret["data"]["code_list"]:
        codes_data.append(
            {
                "items": sub("<.*?>", "", code_info["title"].replace("&nbsp;", " ")),
                "code": code_info["code"],
            }
        )

    return codes_data


async def get_msg(send_target: PlatformTarget, mhy_type) -> MessageFactory:
    """生成最新前瞻直播兑换码合并转发消息"""

    act_id = await get_act_id(mhy_type=mhy_type)
    if not act_id:
        return MessageFactory([Text("暂无前瞻直播资讯！")])

    live_data = await get_live_data(act_id)
    if live_data.get("error"):
        return MessageFactory([Text(live_data["error"])])
    elif live_data.get("start"):
        return MessageFactory([Text(live_data["header"])]) + MessageFactory(
            [Text(live_data["room"])]
        )

    codes_data = await get_codes(live_data["code_ver"], act_id)
    if isinstance(codes_data, Dict):
        return MessageFactory([Text(live_data["error"])])
    codes_msg = MessageFactory(
        [
            Text(
                f"当前发布了 {len(codes_data)} 个兑换码，请在有效期内及时兑换哦~"
                + "\n\n* 官方接口数据有 2 分钟左右延迟，请耐心等待下~"
            )
        ]
    )
    for code in codes_data:
        codes_msg.append((code["code"]))
    if live_data.get("review"):
        codes_msg.append(
            "直播已经结束，查看回放：\n\n"
            + f"https://www.miyoushe.com/ys/article/{live_data['review']}"
        )
    return codes_msg
