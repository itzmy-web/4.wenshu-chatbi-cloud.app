# 问法灵感推荐路由：GET /api/suggest 返回一批示例问法（帮助用户冷启动）
import random

from fastapi import APIRouter
from fastapi.params import Depends

from app.api.routers.auth_router import verify_token

suggest_router = APIRouter()

# 精选问法池（与当前数仓模型 fact_order + dim_* 匹配），每次随机返回 6 条
QUESTION_POOL = [
    "统计2025年各地区销售总额",
    "2025年每个月的订单量趋势",
    "2025年销售额最高的5款产品",
    "2025年消费金额最高的5位客户",
    "2025年各季度的GMV走势",
    "2025年哪个月订单量最少",
    "2025年华东地区卖得最好的产品",
    "2025年下单的客户一共有多少个",
    "2025年平均每笔订单的金额是多少",
    "2025年每个月的GMV是多少",
    "2025年销售额最低的3个地区",
    "2025年销量最高的3款产品",
]

_SUGGEST_COUNT = 6


@suggest_router.get("/api/suggest")
async def suggest(_token: None = Depends(verify_token)):
    """随机返回一批可参考的问法，解决用户不知道能问什么的冷启动问题"""
    return {"suggestions": random.sample(QUESTION_POOL, _SUGGEST_COUNT)}
