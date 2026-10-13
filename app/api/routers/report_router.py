# 每日报告路由：
#   GET  /api/report      读取最近一次缓存的报告（无缓存则现场生成一次）
#   POST /api/report/run  立即重新生成报告并写缓存
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.params import Depends as DependsP

from app.api.dependencies import get_dw_session
from app.api.routers.auth_router import verify_token
from app.core.log import logger

report_router = APIRouter()

# 报告预设问法（与内置示例数仓匹配）
REPORT_QUESTIONS = [
    {"key": "total_sales", "q": "2025年的总销售额是多少", "label": "总销售额", "type": "kpi"},
    {"key": "orders", "q": "2025年总共有多少笔订单", "label": "订单总数", "type": "kpi"},
    {"key": "customers", "q": "2025年下单的客户一共有多少个", "label": "下单客户数", "type": "kpi"},
    {"key": "aov", "q": "2025年平均每笔订单的金额是多少", "label": "平均订单金额", "type": "kpi"},
    {"key": "by_region", "q": "统计2025年各地区销售总额", "label": "各地区销售额", "type": "chart"},
    {"key": "by_month", "q": "2025年每个月的订单量趋势", "label": "月度订单量趋势", "type": "chart"},
]

_REPORT_PATH = Path("data") / "report_cache.json"
_report_lock = asyncio.Lock()


async def generate_report() -> dict:
    """用问数管线跑一遍预设问法，生成报告数据"""
    from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
    from app.api.dependencies import (get_column_qdrant_repository, get_embedding_client,
                                      get_value_es_repository, get_metric_qdrant_repository)
    from app.repositories.es.value_es_repository import ValueEsRepository
    from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
    from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
    from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
    from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
    from app.services.query_service import QueryService

    async with meta_mysql_client_manager.session_factory() as ms, \
            dw_mysql_client_manager.session_factory() as ds:
        service = QueryService(
            embedding_client=await get_embedding_client(),
            column_qdrant_repository=await get_column_qdrant_repository(),
            value_es_repository=ValueEsRepository(),
            metric_qdrant_repository=await get_metric_qdrant_repository(),
            meta_mysql_repository=MetaMysqlRepository(ms),
            dw_mysql_repository=DwMysqlRepository(ds),
        )

        items = []
        for spec in REPORT_QUESTIONS:
            result, insight = [], ""
            async for chunk in service.query(spec["q"]):
                if not chunk.startswith("data:"):
                    continue
                try:
                    m = json.loads(chunk[5:].strip())
                except Exception:
                    continue
                if m.get("result") is not None:
                    result = m["result"]
                if m.get("insight"):
                    insight = m["insight"]
            items.append({**spec, "result": result, "insight": insight})
    report = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "date": datetime.now().strftime("%Y-%m-%d"), "items": items}
    return report


async def _run_and_cache() -> dict:
    async with _report_lock:
        report = await generate_report()
        _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        logger.info(f"每日报告已生成并缓存：{_REPORT_PATH}")
        return report


@report_router.get("/api/report")
async def get_report(_token: None = DependsP(verify_token)):
    if _REPORT_PATH.exists():
        return json.loads(_REPORT_PATH.read_text(encoding="utf-8"))
    return await _run_and_cache()


@report_router.post("/api/report/run")
async def run_report(_token: None = DependsP(verify_token)):
    return await _run_and_cache()


async def daily_report_scheduler():
    """每日 09:00 自动重新生成报告缓存的常驻任务"""
    from app.core.log import logger as _logger
    while True:
        now = datetime.now()
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        try:
            await _run_and_cache()
        except Exception as e:
            _logger.warning(f"每日报告定时生成失败：{e}")
