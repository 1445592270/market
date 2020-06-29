import logging
import requests
from tortoise.query_utils import Q
import datetime
from market.models import StrategyPackage
from market.models.const import OrderStatus,ProductType
from market.models.order import UserOrder
from market.models.user import MarketUser
from market.models.strategy import QStrategy
from market.schemas.order import OrderInfo, OrderSearch, OrderSearchOut

logger = logging.getLogger(__name__)


async def show_order(order_id: int):
    """查看订单详情"""
    order = UserOrder.get_or_none(id=order_id)
    if order:
        return OrderInfo(**order.__dict__)
    return None


async def search_order_fake(schema_in: OrderSearch):

    """搜索用户的订单列表"""
    query = UserOrder.filter(~Q(status=OrderStatus.deleted))
    #print(await query,'555555555555555555555555')
    order_id1 = 0
    query_count = 0
    if schema_in.fuzzy:  # 订单模糊搜索，账户和订单 ID
        users = await MarketUser.filter(phone__contains=schema_in.fuzzy)
        user_ids = [user.id for user in users]
        #print(user_ids,'user_ids1111111111')
        query = UserOrder.filter(user_id__in=user_ids)
        try:
            order_id = int(schema_in.fuzzy)
            order_id1 = order_id
            query = UserOrder.filter(id=order_id)
            query_count = await query.count()
            if (await query.count()) == 0:
                query = UserOrder.filter(user_id__in=user_ids)
        except ValueError:
            pass
    if schema_in.product_id:
        query = UserOrder.filter(product_id=schema_in.product_id)
    if schema_in.product_type:
        query = UserOrder.filter(product_type=schema_in.product_type)
    if schema_in.status:
        query = UserOrder.filter(status=schema_in.status)
    if schema_in.product_type and schema_in.status:
        query = UserOrder.filter(status=schema_in.status,product_type=schema_in.product_type)
    if schema_in.fuzzy and schema_in.product_type:
        if query_count !=0:
            query = UserOrder.filter(id=int(schema_in.fuzzy),product_type=schema_in.product_type,)
        else:
            query = UserOrder.filter(user_id__in=user_ids,product_type=schema_in.product_type,)
    if schema_in.fuzzy and schema_in.status:
        if query_count !=0:
            query = UserOrder.filter(id=int(schema_in.fuzzy),status=schema_in.status,)
        else:
            query = UserOrder.filter(user_id__in=user_ids,status=schema_in.status,)
    if schema_in.product_type and schema_in.status and schema_in.fuzzy:
        if query_count != 0:
            query = UserOrder.filter(status=schema_in.status, product_type=schema_in.product_type,id=order_id1)
        else:
            query = UserOrder.filter(status=schema_in.status, product_type=schema_in.product_type, user_id__in=user_ids)
    total_count = await query.count()
    status_payed = []#统计策略销量-----------------------start
    count_strategy = {}
    for i in (await query):
        if i.status == OrderStatus.payed and i.product_type == ProductType.package:
            status_payed.append(i.product_id)
            strategy_query = await QStrategy.filter(package_id=i.product_id)
            for strategy in strategy_query:
                if not strategy.product_id in count_strategy:
                    count_strategy[strategy.product_id] = 1
                else:
                    count_strategy[strategy.product_id] += 1
    strate1_query = await QStrategy.filter(package_id__in = status_payed)
    #print(strate1_query,'strate1_query')
    #print(count_strategy,'count_strategy11111111111111111111')
    for i in strate1_query:
        i.sell_cnt = count_strategy[(i.product_id)]
        await i.save()#-------------------------end
    orders = (
            await query.order_by("id")
            .offset(schema_in.offset)
            .limit(schema_in.count)
            .prefetch_related("user")
            )
    data = []
    #print(orders,'orders')
    for order in orders:
        #print(11111111111111111111)
        #order.create_dt = order.create_dt+datetime.timedelta(hours=8)
        package_name = await StrategyPackage.get(product_id=order.product_id)
        if order.user:
            #print(2222222222222222222222)
            info = {
                    "user_id": order.user.id,
                    "user_name": order.user.name,
                    "user_phone": order.user.phone,
                    "package_name": package_name.name,
                    }
        else:
            #print(33333333333333333)
            info = {"user_id": -1, "user_name": "deleted", "user_phone": "100000000000","package_name":''}
        info.update(order.__dict__)
        data.append(info)
    #print(data,'data11111111111111111111')
    return OrderSearchOut(total=total_count, data=data)

async def search_order(schema_in: OrderSearch):
    """搜索用户的订单列表"""
    query = UserOrder.filter(~Q(status=OrderStatus.deleted))
    order_id1 = 0
    if schema_in.fuzzy:  # 订单模糊搜索，账户和订单 ID
        users = await MarketUser.filter(
            Q(phone__contains=schema_in.fuzzy)
            | Q(email__contains=schema_in.fuzzy)
            | Q(email__contains=schema_in.fuzzy),
        )
        user_ids = [user.id for user in users]
        query = UserOrder.filter(user_id__in=user_ids)
        try:
            order_id = int(schema_in.fuzzy)
            order_id1 = order_id
            query = UserOrder.filter(id=order_id)
        except ValueError:
            pass
    if schema_in.order_id:
        query = UserOrder.filter(id=schema_in.order_id)
    if schema_in.user_id:
        query = UserOrder.filter(user_id=schema_in.user_id)
    if schema_in.product_id:
        query = UserOrder.filter(product_id=schema_in.product_id)
    if schema_in.product_type:
        query = UserOrder.filter(product_type=schema_in.product_type)
    if schema_in.status:
        query = UserOrder.filter(status=schema_in.status,user_id=schema_in.user_id)
    if schema_in.product_type and schema_in.status:
        query = UserOrder.filter(status=schema_in.status,product_type=schema_in.product_type)
    if schema_in.product_type and schema_in.status and schema_in.fuzzy:
        query = UserOrder.filter(status=schema_in.status, product_type=schema_in.product_type,id=order_id1)
    total_count = await query.count()
    orders = (
        await query.order_by("id")
        .offset(schema_in.offset)
        .limit(schema_in.count)
        .prefetch_related("user")
    )
    data = []
    for order in orders:
        #order.create_dt = order.create_dt+datetime.timedelta(hours=8)
        package_name = await StrategyPackage.get(product_id=order.product_id)
        if order.user:
            info = {
                "user_id": order.user.id,
                "user_name": order.user.name,
                "user_phone": order.user.phone,
                "package_name": package_name.name,
            }
        else:
            info = {"user_id": -1, "user_name": "deleted", "user_phone": "100000000000","package_name": ' '}
        info.update(order.__dict__)
        data.append(info)
    return OrderSearchOut(total=total_count, data=data)


#匹配用户累计策略费用
async def request_url(total_cash1):
    #url = 'http://192.168.1.222:8888/wk/api/a/user/accumulatedUserStrategyCost'
    url = 'https://account.acequant.cn/wk/api/a/user/accumulatedUserStrategyCost'  #线上环境地址
    #url = 'http://fpjieu.natappfree.cc/wk/api/a/user/accumulatedUserStrategyCost'
    data = total_cash1
    #print(data,'total_cash data')
    headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.122 Safari/537.36',
            'Content-Type': 'application/json',
            'requestSource': 'requestFromStrategySupermarket'
            }
    res = requests.post(url, headers=headers, json=data,verify=False)
    return res.text




#匹配用户套餐购买记录
async def requests_url(api_info):
    # url = 'http://192.168.1.222:8888/wk/api/a/user/matchUserPackagePurchaseRecords'#测试环境
    #url='http://fpjieu.natappfree.cc/wk/api/a/user/matchUserPackagePurchaseRecords'#测试用穿透地址
    url = 'https://account.acequant.cn/wk/api/a/user/matchUserPackagePurchaseRecords'#线上环境
    data = {
            "phone":str(api_info['phone']),
            "actuallyPaid":str(api_info['actuallyPaid']),
            "completeTime":int(api_info['completeTime']),
            "costOfProduction":str(api_info['costOfProduction']),
            "orderNumber":str(api_info['orderNumber']),
            "orderStatus":str(api_info['orderStatus']),
            "packageName":str(api_info['packageName']),
            "paymentMethod":str(api_info['paymentMethod']),
            }
    headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.122 Safari/537.36',
            'Content-Type':'application/json',
            'requestSource':'requestFromStrategySupermarket'
            }
    res = requests.post(url,headers = headers ,json=data)
    return res.text
