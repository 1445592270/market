import datetime
import time
import logging
from typing import Any, Dict
from uuid import UUID
from tortoise.query_utils import Q
from fastapi import APIRouter, Depends, HTTPException, status
from starlette.requests import Request
from tortoise import Tortoise
from tortoise.exceptions import DoesNotExist

from market.api.share.run_info import (
    get_curves,
    get_indicators,
    get_period_returns,
    get_portfolio_info,
    get_today_positons,
    get_today_returns,
)
from market.api.share.strategy import sortedd,search_strategy_package
from market.api.share.strategy import check_task_permission, search_strategy
from market.const import TaskType
from market.core.security import require_active_user
from market.models.const import ListStatus, ProductType,OrderStatus
from market.models.order import UserOrder
from market.models.strategy import QStrategy
from market.models.package import StrategyPackage
from market.models.user import MarketUser
from market.schemas.base import CommonOut,BaseSearch
from market.schemas.runinfo import PortfolioRatio
from market.schemas.strategy import BuyedQStrategySearch  # QStrategyInfo,
from market.schemas.strategy import (
    BuyedQStrategyInfo,
    BuyedQStrategySearchOut,
    QStrategyBasicInfo,
    QStrategySearch,
    QStrategySearchOut,
    QStrategySearchOVOut,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/strategy/check/{task_id}", response_model=CommonOut, tags=["用户端——策略运行信息"]
)
async def check_buyed(task_id: str, request: Request):
    """检查是否需要因此策略信息"""
    try:
        if await check_task_permission(TaskType.PAPER_TRADING, task_id, request):
            return CommonOut()
    except Exception:
        pass
    return CommonOut(errCode=-1, errMsg="没有权限")


@router.post("/strategy/copy/{task_id}", response_model=CommonOut, tags=["用户端——策略运行信息"])
async def get_strategy_code(task_id: str, request: Request):
    """检查是否需要因此策略信息"""
    if not await check_task_permission(TaskType.PAPER_TRADING, task_id, request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "没有权限")
    # # get code
    # query_str = "SELECT backtest_id FROM wk_simulation WHERE task_id=%s"
    # client = Tortoise.get_connection("qpweb")
    # try:
    #     rows = await client.execute_query_dict(query_str, task_id)
    # except TypeError:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="复制错误，策略已不存在")
    # if len(rows) != 1:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="复制错误，策略已不存在")
    # backtest_id = rows[0]["backtest_id"]
    #
    # query_str = f"SELECT code FROM wk_strategy_backtest WHERE id=%s"
    # try:
    #     rows = await client.execute_query_dict(query_str, backtest_id)
    # except TypeError:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="复制错误，策略已不存在")
    # if len(rows) != 1:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="复制错误，策略已不存在")
    #
    # code = rows[0]["code"]
    # return CommonOut(data=code)
    strategy_limit = await QStrategy.get(task_id=task_id)
    package_limit = await StrategyPackage.get(product_id=strategy_limit.package_id)
    if (int(time.time()) - int(strategy_limit.limit_interval)) > int(package_limit.limit_interval):
        strategy_limit.limit_interval = int(time.time())
        await strategy_limit.save()
        query_str = "SELECT backtest_id FROM wk_simulation WHERE task_id=%s"
        client = Tortoise.get_connection("qpweb")
        try:
            rows = await client.execute_query_dict(query_str, task_id)
        except TypeError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="复制错误，策略已不存在")
        if len(rows) != 1:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="复制错误，策略已不存在")
        backtest_id = rows[0]["backtest_id"]

        query_str = f"SELECT code FROM wk_strategy_backtest WHERE id=%s"
        try:
            rows = await client.execute_query_dict(query_str, backtest_id)
        except TypeError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="复制错误，策略已不存在")
        if len(rows) != 1:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="复制错误，策略已不存在")
        code = rows[0]["code"]
        return CommonOut(data=code)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="复制间隔时间过短,请过%s秒再次复制" % ((int(time.time()) - int(strategy_limit.limit_interval))-int(package_limit.limit_interval)))

@router.get(
    "/strategy/portfolio/{product_id}",
    response_model=PortfolioRatio,
    tags=["用户端——策略信息"],
)
async def get_portfolio(product_id: UUID):
    """获取策略仓位占比信息"""
    try:
        strategy = await QStrategy.get(product_id=product_id, status=ListStatus.online)
    except DoesNotExist:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未找到该策略")
    portfolio_info = await get_portfolio_info(TaskType.PAPER_TRADING, strategy.task_id)
    positions = await get_today_positons(TaskType.PAPER_TRADING, strategy.task_id)
    try:
        pos_ratio = round(
            float(portfolio_info["positions_value"])
            / float(portfolio_info["net_value"]),
            2,
        )
    except (ZeroDivisionError, KeyError):
        pos_ratio = 0.0
    return {
        "name": strategy.name,
        "task_id": strategy.task_id,
        "start_cash": portfolio_info.get("start_cash", 0),
        "net_value": portfolio_info.get("net_value", 0),
        "positions_value": portfolio_info.get("positions_value", 0),
        "hold_ratio": pos_ratio,
        "pos_cnt": len(positions),
        "start_dt": strategy.sim_start_dt,
    }


@router.get(
    "/strategy/show/{product_id}", response_model=QStrategyBasicInfo, tags=["用户端——策略信息"]
)
async def get_strategy_info(product_id: UUID):
    """获取策略概览信息"""
    try:
        strategy = await QStrategy.get(product_id=product_id, status=ListStatus.online)
    except DoesNotExist:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未找到该策略")
    client = Tortoise.get_connection("qpweb")
    row = await client.execute_query_dict(
            "SELECT nick_name FROM wk_user WHERE id=%s", strategy.user_id
            )
    if len(row) == 0:
        raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="姓名查找失败！！！"
                )
    nick_name = row[0]["nick_name"]
    author_name=nick_name
    if strategy.author_name !=nick_name:
        await QStrategy.filter(product_id=product_id,status=ListStatus.online).update(author_name=nick_name)
    data = {
        "product_id": strategy.product_id,
        "name": strategy.name,
        #"newest_worth": newest_worth,
        "style": strategy.style,
        "category": strategy.category,
        "tags": strategy.tags,
        "author_name": author_name,
        "ideas": strategy.ideas,
        "desc": strategy.desc,
        "buyout_price": strategy.buyout_price,
        "task_id": strategy.task_id,
        #"sell_cnt": strategy.sell_cnt_show+strategy.sell_cnt,
        "sell_cnt": strategy.total_cnt if (strategy.sell_cnt_show+strategy.sell_cnt) >strategy.total_cnt else (strategy.sell_cnt_show+strategy.sell_cnt),
        "total_cnt": strategy.total_cnt,
        "sim_start_dt": strategy.sim_start_dt,
        "online_dt": strategy.online_dt,
        "period_prices": strategy.period_prices,
        "enable_discount": strategy.enable_discount,
        "discount_info": strategy.discount_info,
        "allow_coupon": strategy.allow_coupon,
        "suit_money": strategy.suit_money,
    }
    indicators = await get_indicators(TaskType.PAPER_TRADING, strategy.task_id)
    data.update(indicators)
    return_info = await get_today_returns(TaskType.PAPER_TRADING, strategy.task_id)
    if return_info:
        data.update(return_info[0])
    data["unv"] = round(data.get("returns", 0) + 1, 2)
    period_returns = await get_period_returns(strategy.task_id)
    data.update(period_returns)
    return data


@router.post(
    "/strategy/list", response_model=BuyedQStrategySearchOut, tags=["用户端——策略信息"]
)
async def list_strategies(
    #schema_in: BuyedQStrategySearch,
    schema_in:BaseSearch,
    current_user: MarketUser = Depends(require_active_user),
):
    """列出已购买策略"""
    fuzzy = schema_in.fuzzy
    query = await UserOrder.filter(
             product_type=ProductType.package,status=OrderStatus.payed
               )

    # product_ids = []
    # order_info_dict = {}
    # for order in query:
    #     product_ids.append(order.product_id)
    #     order_info_dict[order.product_id] = {
    #         "order_id": order.id,
    #         "total_cash": order.total_cash,
    #         "total_days": order.total_days,
    #         "days": order.days,
    #         "gift_days": order.gift_days,
    #         "coupon_days": order.coupon_days,
    #         "coupon_cash": order.coupon_cash,
    #         "payed_cash": order.payed_cash,
    #         "expire_dt": order.expire_dt,
    #         "create_dt": order.create_dt,
    #         "pay_dt": order.pay_dt,
    #     }
    # print(product_ids,'product_idsproduct_idsproduct_idsproduct_idsproduct_ids')
    # print(order_info_dict,'order_info_dictorder_info_dictorder_info_dictorder_info_dict')

    product_ids = []
    order_info_dict = {}
    dd = {}  # 统计订单中的每个套餐的次数
    idd = []  # 所有product_id
    query1 = await UserOrder.filter(user_id=current_user.id, status=OrderStatus.payed)
    if query1:
        for i in query1:
            idd.append(i.product_id)
    else:
        return BuyedQStrategySearchOut(total=0, data=[], )
    for order in query:
        product_ids.append(order.product_id)
        for j in idd:
            dd.update({(order.product_id): idd.count(j)})
        num = int(dd[order.product_id])
        for k1, v1 in dd.items():
            if v1 == 1:
                order_info_dict[order.product_id] = {
                    "order_id": order.id,
                    "total_cash": order.total_cash,
                    "total_days": order.total_days,
                    "days": order.days,
                    "gift_days": order.gift_days,
                    "coupon_days": order.coupon_days,
                    "coupon_cash": order.coupon_cash,
                    "payed_cash": order.payed_cash,
                    "expire_dt": order.expire_dt,
                    "create_dt": order.create_dt,
                    "pay_dt": order.pay_dt,
                }
            else:
                package_pro = await StrategyPackage.get(product_id=order.product_id)
                expire_dt_list = package_pro.period_prices
                day=int(expire_dt_list[0]['day'])
                # gift_day=int(expire_dt_list[0]['gift_day'])
                expire_dt_all = order.create_dt+datetime.timedelta(days=num*(day))
                order_info_dict[package_pro.product_id] = {
                    "order_id": order.id,
                    "total_cash": order.total_cash,
                    "total_days": order.total_days,
                    "days": order.days,
                    "gift_days": order.gift_days,
                    "coupon_days": order.coupon_days,
                    "coupon_cash": order.coupon_cash,
                    "payed_cash": order.payed_cash,
                    "expire_dt": expire_dt_all,
                    "create_dt": order.create_dt,
                    "pay_dt": order.pay_dt,
                }
    strategy_list_count = await QStrategy.filter(package_id__in=product_ids,status=ListStatus.online).count()
    total_count = strategy_list_count
    if not schema_in.fuzzy:
        strategy_list = await QStrategy.filter(
                        package_id__in=product_ids, status=ListStatus.online
                            ).offset(schema_in.offset).limit(schema_in.count)
    else:
        strategy_list = await QStrategy.filter(
                        package_id__in=product_ids, status=ListStatus.online,name__contains=schema_in.fuzzy
                        ).offset(schema_in.offset).limit(schema_in.count)
    strategy_list1 = []
    strategy_list2 = []
    for j in strategy_list:
        strategy_list1.append(j)
    data = []
    for i in strategy_list1:
        if i not in strategy_list2:
            strategy_list2.append(i)
    for strategy in strategy_list2:
        info = dict(**strategy.__dict__)
        info.update(**order_info_dict[strategy.package_id])
        data.append(BuyedQStrategyInfo(**info))
    return BuyedQStrategySearchOut(total=total_count, data=data,)

@router.post("/strategy/find", response_model=QStrategySearchOut, tags=["用户端——策略信息"])
async def user_search_strategy(schema_in: QStrategySearch):
    """搜索策略"""
    return await search_strategy(schema_in)


@router.post(
    "/strategy/find/ov", response_model=QStrategySearchOVOut, tags=["用户端——策略信息"]
)
async def strategy_overview(schema_in: QStrategySearch):
    """首页策略列表"""
    task_id = schema_in.task_id
    package_id = schema_in.package_id
    sort = schema_in.sort
    fuzzy = schema_in.fuzzy
    if not fuzzy:
        if not package_id:
            strategies = await search_strategy_package(schema_in)
            total_cnt = 0
            data = []
            for strategy in strategies:
                total_cnt += 1
                indicators = await get_indicators(TaskType.PAPER_TRADING, strategy.task_id)
                _, curve = await get_curves(TaskType.PAPER_TRADING, strategy.task_id)
                return_info = await get_today_returns(TaskType.PAPER_TRADING, strategy.task_id)
                info: Dict[str, Any] = {"curve": [], "bench_curve": []}
                for daily_curve in curve:
                    info["curve"].append((daily_curve["day"], daily_curve["returns"]))
                    info["bench_curve"].append(
                        (daily_curve["day"], daily_curve["bench_returns"])
                    )
                info.update(indicators)
                if return_info:
                    info.update(return_info[0])
                info.update(strategy.__dict__)
                data.append(info)
            #print(data,'444444444444444444444444')
            total_cnt, sort_cum = await sortedd(data, total_cnt, sort)
            return QStrategySearchOVOut(total=total_cnt, data=sort_cum[schema_in.offset:schema_in.count+schema_in.offset])
        else:
            strategies = await search_strategy_package(schema_in)
            total_cnt = 0
            data = []
            for strategy in strategies:
                total_cnt += 1
                indicators = await get_indicators(TaskType.PAPER_TRADING, strategy.task_id)
                _, curve = await get_curves(TaskType.PAPER_TRADING, strategy.task_id)
                return_info = await get_today_returns(TaskType.PAPER_TRADING, strategy.task_id)
                info: Dict[str, Any] = {"curve": [], "bench_curve": []}
                for daily_curve in curve:
                    info["curve"].append((daily_curve["day"], daily_curve["returns"]))
                    info["bench_curve"].append(
                            (daily_curve["day"], daily_curve["bench_returns"])
                            )
                info.update(indicators)
                if return_info:
                    info.update(return_info[0])
                info.update(strategy.__dict__)
                data.append(info)
            total_cnt, sort_cum = await sortedd(data, total_cnt, sort)
            return QStrategySearchOVOut(total=total_cnt, data=sort_cum)
    else:  # fuzzy存在
        if not package_id:
            strategies = await search_strategy_package(schema_in)
            total_cnt = 0
            data = []
            for strategy in strategies:
                total_cnt += 1
                indicators = await get_indicators(TaskType.PAPER_TRADING, strategy.task_id)
                _, curve = await get_curves(TaskType.PAPER_TRADING, strategy.task_id)
                return_info = await get_today_returns(TaskType.PAPER_TRADING, strategy.task_id)
                info: Dict[str, Any] = {"curve": [], "bench_curve": []}
                for daily_curve in curve:
                    info["curve"].append((daily_curve["day"], daily_curve["returns"]))
                    info["bench_curve"].append(
                        (daily_curve["day"], daily_curve["bench_returns"])
                    )
                info.update(indicators)
                if return_info:
                    info.update(return_info[0])
                info.update(strategy.__dict__)
                data.append(info)
            total_cnt, sort_cum = await sortedd(data, total_cnt, sort)
            return QStrategySearchOVOut(total=total_cnt, data=sort_cum)
        else:
            strategies = await search_strategy_package(schema_in)
            total_cnt = 0
            data = []
            for strategy in strategies:
                total_cnt += 1
                indicators = await get_indicators(TaskType.PAPER_TRADING, strategy.task_id)
                _, curve = await get_curves(TaskType.PAPER_TRADING, strategy.task_id)
                return_info = await get_today_returns(TaskType.PAPER_TRADING, strategy.task_id)
                info: Dict[str, Any] = {"curve": [], "bench_curve": []}
                for daily_curve in curve:
                    info["curve"].append((daily_curve["day"], daily_curve["returns"]))
                    info["bench_curve"].append(
                        (daily_curve["day"], daily_curve["bench_returns"])
                    )
                info.update(indicators)
                if return_info:
                    info.update(return_info[0])
                info.update(strategy.__dict__)
                data.append(info)
            total_cnt, sort_cum = await sortedd(data, total_cnt, sort)
            return QStrategySearchOVOut(total=total_cnt, data=sort_cum)
