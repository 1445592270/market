import datetime
import logging
from typing import List, Union
from uuid import UUID

from starlette.requests import Request
from tortoise.query_utils import Q

from market.const import TaskType
from market.core.security import api_key_schema, get_active_user
from market.models.const import ListStatus, OrderStatus, ProductType
from market.models.order import UserOrder
from market.models.strategy import QStrategy
from market.models.user import MarketUser
from market.schemas.base import CommonOut
from market.schemas.strategy import (
    QStrategyInfo,
    QStrategySearch,
    QStrategySearchOut,
    QStrategyUpdateFields,
)

logger = logging.getLogger(__name__)


async def check_task_permission(task_type: TaskType, task_id: str, request: Request):
    """检查用户是否有该策略的权限"""
    try:
        current_user: MarketUser = await get_active_user(request)
    except Exception:
        logger.warning("check_task_permission no active user found")
        return False
    if task_type == TaskType.PAPER_TRADING:
        product = await QStrategy.get_or_none(task_id=task_id,status=ListStatus.online)
        #product = await QStrategy.filter(task_id=task_id)
    else:
        product = await QStrategy.get_or_none(bt_task_id=task_id)
    if not product:
        logger.warning("check_task_permission no product found")
        return False
    #for i in product:
    #    user_order = await UserOrder.filter(
    #            user_id=current_user.id,
    #            product_type=ProductType.package,
    #            product_id=i.package_id,
    #            status=OrderStatus.payed,
    #            expire_dt__gt=datetime.datetime.now(),
    #            )
    #    if user_order:
    #        logger.info('success')
    #        return True
    #    return False
    user_order = await UserOrder.filter(
        user__id=current_user.id,
        product_type=ProductType.package,
        product_id=product.package_id,
        status=OrderStatus.payed,
        expire_dt__gt=datetime.datetime.now(),
    )
    if user_order:
        logger.warning("check_task_permission yes user order found")
        return True
    #return False
    return True

async def show_strategy(strategy_id: UUID):
    """查看策略"""
    strategy = await QStrategy.get_or_none(product_id=strategy_id)
    if not strategy:
        return CommonOut(errCode=-1, errMsg="没找到该策略")
    return QStrategyInfo(**strategy.__dict__)


async def edit_strategy(product_id: str, changed: QStrategyUpdateFields):
    """编辑上架策略"""
    try:
        await QStrategy.filter(product_id=product_id).update(**changed.dict())
    except Exception:
        logger.exception("更新策略 (%s) 失败：%s", product_id, changed.json())
        return CommonOut(errCode=-1, errMsg="更新失败，请检查名字是否重复")
    return CommonOut()


async def change_strategy_status(id_list: Union[str, List[str]], status: ListStatus):
    """直接重新上架策略"""
    if isinstance(id_list, str):
        id_list = [id_list]
    await QStrategy.filter(product_id__in=id_list).update(status=status,update_dt=datetime.datetime.now()-datetime.timedelta(hours=8))
    return CommonOut()


async def search_strategy(schema_in: QStrategySearch, return_strategy_list=False):
    """搜索策略"""
    # TODO: support tag search, perphaps need to use raw sql
    # from tortoise import Tortoise
    # con = Tortoise.get_connection()
    # await con.execute()


    query = QStrategy.filter()
    #print(schema_in.fuzzy,'3333333333333333333')
    if schema_in.status:
        query = query.filter(status=schema_in.status)
    else:
        query = query.filter(status=ListStatus.online)
    if schema_in.product_id:
        query = query.filter(product_id=schema_in.product_id)
    if schema_in.market_id:
        query = query.filter(market__id=schema_in.market_id)
    if schema_in.package_id:
        query = query.filter(package__id=schema_in.package_id,status=ListStatus.online)
    if schema_in.task_id:
        query = query.filter(task_id__contains=schema_in.task_id)
    if schema_in.style:
        query = query.filter(style__contains=schema_in.style)
    if schema_in.category:
        query = query.filter(category__contains=schema_in.category)
    if schema_in.name:
        query = query.filter(name__contains=schema_in.name)
    if schema_in.fuzzy:
        #query = query.filter(name__contains=schema_in.fuzzy)
        query = query.filter(Q(name__contains=schema_in.fuzzy,status=ListStatus.online) | Q(product_id__contains=schema_in.fuzzy) | Q(author_name__contains=schema_in.fuzzy,status=ListStatus.online))
    total_count = await query.count()
    if schema_in.offset ==0:
        strategy_list1 = (
            await query.order_by("-name").offset(schema_in.offset)
        )
    else:
        strategy_list1 = (await query.order_by("name").offset(schema_in.offset+total_count))
    strategy_list = []
    for i in strategy_list1:
        if i not in strategy_list:
            strategy_list.append(i)
    if return_strategy_list:
        return  total_count,strategy_list
    return QStrategySearchOut(
        total = total_count,data=[strategy for strategy in strategy_list],
    )


async def search_strategy_package(schema_in: QStrategySearch):
    """搜索策略"""
    if schema_in.package_id:
        if schema_in.status:
            strategies = await QStrategy.filter(package_id = schema_in.package_id,status=schema_in.status)
        else:
            strategies = await QStrategy.filter(package_id = schema_in.package_id,status=ListStatus.online)
    else:
        if schema_in.status:
            strategies = await QStrategy.filter(status=schema_in.status)
        else:
            strategies = await QStrategy.filter(status=ListStatus.online)
    if schema_in.product_id:
        strategies = await QStrategy.filter(product_id=schema_in.product_id)
    if schema_in.market_id:
        strategies = await QStrategy.filter(market_id=schema_in.market_id)
    if schema_in.package_id:
        strategies = await QStrategy.filter(package_id=schema_in.package_id, status=ListStatus.online)
    if schema_in.task_id:
        strategies = await QStrategy.filter(task_id__contains=schema_in.task_id)
    if schema_in.style:
        strategies = await QStrategy.filter(style__contains=schema_in.style)
    if schema_in.category:
        strategies = await QStrategy.filter(category__contains=schema_in.category)
    if schema_in.name:
        strategies = await QStrategy.filter(name__contains=schema_in.name)
    if schema_in.fuzzy:
        strategies = await QStrategy.filter(
            Q(name__contains=schema_in.fuzzy, status=ListStatus.online) | Q(author_name__contains=schema_in.fuzzy,status=ListStatus.online))
    if schema_in.package_id and schema_in.style:
        strategies = await QStrategy.filter(package_id=schema_in.package_id, style__contains=schema_in.style)
    if schema_in.package_id and schema_in.style and schema_in.fuzzy:
        strategies = await QStrategy.filter(package_id=schema_in.package_id, style__contains=schema_in.style,
                                            name__contains=schema_in.fuzzy)
    return strategies

async def search_strategy_fake(schema_in: QStrategySearch):
    order_bys = schema_in.order_bys
    query = QStrategy.filter()
    if schema_in.status:
        query = query.filter(status=schema_in.status)
    else:
        query = query.all()
    if schema_in.product_id:
        query = query.filter(product_id=schema_in.product_id)
    if schema_in.market_id:
        query = query.filter(market__id=schema_in.market_id)
    if schema_in.package_id:
        query = query.filter(package__id=schema_in.package_id,status=ListStatus.online)
    if schema_in.task_id:
        query = query.filter(task_id__contains=schema_in.task_id)
    if schema_in.style:
        query = query.filter(style__contains=schema_in.style)
    if schema_in.category:
        query = query.filter(category=schema_in.category)
    if schema_in.name:
        query = query.filter(name__contains=schema_in.name)
    if schema_in.fuzzy:
        query = query.filter(Q(name__contains=schema_in.fuzzy) | Q(product_id__contains=schema_in.fuzzy) | Q(author_name__contains=schema_in.fuzzy))
    total_count = await query.count()
    if not order_bys:
        strategy_list = (await query.order_by('name').offset(schema_in.offset).limit(schema_in.count))
    else:
        if order_bys[0] == 'create_dt':
            strategy_list = await query.order_by("create_dt")
        elif order_bys[0] == '-create_dt':
            strategy_list = await query.order_by("-create_dt").offset(schema_in.offset).limit(schema_in.count)
        elif order_bys[0] == 'total_cnt':
            strategy_list = await query.order_by("total_cnt").offset(schema_in.offset).limit(schema_in.count)
        elif order_bys[0] == '-total_cnt':
            strategy_list = await query.order_by("-total_cnt").offset(schema_in.offset).limit(schema_in.count)
        elif order_bys[0] == 'sell_cnt':
            strategy_list = await query.order_by("sell_cnt").offset(schema_in.offset).limit(schema_in.count)
        elif order_bys[0] == '-sell_cnt':
            strategy_list = await query.order_by("-sell_cnt").offset(schema_in.offset).limit(schema_in.count)
        elif order_bys[0] == 'suit_money':
            strategy_list = (await query.order_by('suit_money').offset(schema_in.offset).limit(schema_in.count))
        elif order_bys[0] == '-suit_money':
            strategy_list = (await query.order_by('-suit_money').offset(schema_in.offset).limit(schema_in.count))
        else:
            strategy_list = await query.order_by("-name").offset(schema_in.offset).limit(schema_in.count)
    return QStrategySearchOut(
            total=total_count, data=[strategy for strategy in strategy_list],
            )


async def sortedd(data,total_cnt,sort):
    info2 = []
    info1 = []
    task = []#存在cum_returns
    task2 = []
    for i in data:
        if 'cum_returns' not in i.keys():
            info1.append(i)
        else:
            task.append(i)
    for cash in data:
        if 'sim_start_cash' not in cash.keys():
            info2.append(cash)
        else:
            task2.append(cash)
    if sort == '1':
        sort_cum = sorted(task, key=lambda s: s['cum_returns'], reverse=False)
        for j in info1:
            sort_cum.append(j)
        return (total_cnt,sort_cum)
    elif sort == '-1':
        sort_cum = sorted(task, key=lambda s: s['cum_returns'], reverse=True)
        for j in info1:
            sort_cum.append(j)
        return (total_cnt, sort_cum)
    elif sort == '2':
        sort_cum = sorted(task, key=lambda s: s['daily_returns'], reverse=False)
        for j in info1:
            sort_cum.append(j)
        return (total_cnt, sort_cum)
    elif sort == '-2':
        sort_cum = sorted(task, key=lambda s: s['daily_returns'], reverse=True)
        for j in info1:
            sort_cum.append(j)
        return (total_cnt, sort_cum)
    elif sort == '3':
        sort_cum = sorted(task, key=lambda s: s['annual_returns'], reverse=False)
        for j in info1:
            sort_cum.append(j)
        return (total_cnt, sort_cum)
    elif sort == '-3':
        sort_cum = sorted(task, key=lambda s: s['annual_returns'], reverse=True)
        for j in info1:
            sort_cum.append(j)
        return (total_cnt, sort_cum)
    elif sort == '4':
        sort_cum = sorted(task, key=lambda s: s['max_drawdown'], reverse=False)
        for j in info1:
            sort_cum.append(j)
        return (total_cnt, sort_cum)
    elif sort == '-4':
        sort_cum = sorted(task, key=lambda s: s['max_drawdown'], reverse=True)
        for j in info1:
            sort_cum.append(j)
        return (total_cnt, sort_cum)
    elif sort == '5':
        sort_cum = sorted(task2, key=lambda s: s['sim_start_cash'], reverse=False)
        for j in info2:
            sort_cum.append(j)
        return (total_cnt, sort_cum)
    elif sort == '-5':
        sort_cum = sorted(task2, key=lambda s: s['sim_start_cash'], reverse=True)
        for j in info2:
            sort_cum.append(j)
        return (total_cnt, sort_cum)
    else:
        sort_cum = sorted(task, key=lambda s: s['cum_returns'], reverse=True)
        for j in info1:
            sort_cum.append(j)
        return (total_cnt, sort_cum)