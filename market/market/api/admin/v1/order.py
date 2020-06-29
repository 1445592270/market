import datetime
import time
import logging
from market.api.share.order import requests_url,request_url
from fastapi import APIRouter, Depends, HTTPException
from tortoise.exceptions import DoesNotExist

from market.api.share.order import search_order, show_order,search_order_fake
from market.core.security import require_super_scope_admin
from market.models.admin_user import MarketAdminUser
from market.models.const import OrderStatus, PayMethod
from market.models.order import UserOrder
from market.models.strategy import QStrategy
from market.models.package import StrategyPackage
from market.models.user import MarketUser
from market.schemas.base import CommonOut
from market.schemas.order import OrderInfo, OrderSearch, OrderSearchOut

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/order/search", response_model=OrderSearchOut, tags=["后台——订单管理"])
async def admin_search_order(
    schema_in: OrderSearch,
    #current_user: MarketAdminUser = Depends(require_super_scope_admin),
):
    """策略上架申请"""
    return await search_order_fake(schema_in)


@router.get("/order/{order_id}", response_model=OrderInfo, tags=["后台——订单管理"])
async def admin_show_order(
    order_id: int, current_user: MarketAdminUser = Depends(require_super_scope_admin)
):
    """查看标签或者风格"""
    return await show_order(order_id)


@router.post("/pay/confirm/{order_id}", response_model=CommonOut, tags=["后台——订单管理"])
async def confirm_pay(
    schema_in:OrderSearch,
    order_id: int, 
    current_user: MarketAdminUser = Depends(require_super_scope_admin)
):
    """确认支付（线下订单）"""
    api_info = {}
    try:
        order = await UserOrder.get(id=order_id)
    except DoesNotExist:
        raise HTTPException(404, detail="订单未找到")
    if order.pay_method != PayMethod.offline:
        raise HTTPException(400, detail="仅线下支付订单支持支付确认")
    if order.status != OrderStatus.unpayed:
        raise HTTPException(400, detail="订单已支付 / 取消")
    order.payed_cash = order.pay_cash
    order.pay_dt = datetime.datetime.now()
    order.expire_dt = datetime.datetime.now() + datetime.timedelta(
        days=order.total_days + order.coupon_days
    )
    order.status = OrderStatus.payed
    await order.save()
    await search_order_fake(schema_in)
    await search_order(schema_in)
    total_cash = []
    total_cash1 = {}
    order1 = await UserOrder.filter(user_id=order.user_id,status=OrderStatus.payed).prefetch_related('user')
    for i in order1:
        total_cash.append(i.total_cash)
        total_cash1.update({"phone":str(i.user.phone)})
    total_cash1.update({"strategicCost":str(sum(total_cash))})
    ress = await request_url(total_cash1)
    print(order.user_id,'user_id')
    print(order_id,'user_id22222222222222222')
    print(order1,'order11111111111111111111')
    print(total_cash1,'total_cash1')
    #print(ress,'ress')
    product = {}
    strategy_list = await StrategyPackage.filter(product_id=order.product_id)
    for i in strategy_list:
        product.update({'name':i.name})
    user_phone = await MarketUser.get(id = order.user_id)
    api_info.update({
        'phone': user_phone.phone,
        'actuallyPaid': order.payed_cash,
        'completeTime': int(time.time() * 1000),
        'costOfProduction': order.pay_cash,
        'orderNumber': order.id,
        'orderStatus': '支付成功',
        'packageName': product['name'],
        'paymentMethod': '线下支付',
        }
        )
    print(api_info, 'fake_api_info')
    res = await requests_url(api_info)
    print(res, 'res444444444444444')
    return CommonOut()


@router.post("/pay/cancel/{order_id}", response_model=CommonOut, tags=["后台——订单管理"])
async def cancel_pay(
    order_id: int, current_user: MarketAdminUser = Depends(require_super_scope_admin)
):
    """取消支付（线下订单）"""
    api_info = {}
    try:
        order = await UserOrder.get(id=order_id)
    except DoesNotExist:
        raise HTTPException(404, detail="订单未找到")
    if order.pay_method != PayMethod.offline:
        raise HTTPException(400, detail="仅线下支付订单支持支付确认")
    if order.status != OrderStatus.unpayed:
        raise HTTPException(400, detail="订单已支付 / 取消")
    order.status = OrderStatus.calceled
    await order.save()
    product = {}
    strategy_list = await StrategyPackage.filter(product_id=order.product_id)
    for i in strategy_list:
        product.update({'name':i.name})
    user_phone = await MarketUser.get(id = order.user_id)
    api_info.update({
        'phone': user_phone.phone,
        'actuallyPaid': order.payed_cash,
        'completeTime': int(time.time() * 1000),
        'costOfProduction': order.pay_cash,
        'orderNumber': order.id,
        'orderStatus': '取消支付',
        'packageName': product['name'],
        'paymentMethod': '线下支付',
        })
    res = await requests_url(api_info)
    print(res, 'res66666666666666')
    return CommonOut()
