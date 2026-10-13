import asyncio

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.clients import external_db
from app.core.log import logger


async def execute_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    # 获取流式输出器
    writer = runtime.stream_writer
    # 输出进度状态信息
    # writer("执行SQL")
    writer({"stage": "执行SQL"})
    try:

        # 获取sql
        sql = state["sql"]
        # 若 SQL 引用了外部直连库的表 → 路由到外部 MySQL 执行；否则查内置数仓
        if external_db.is_external_sql(sql):
            logger.info("SQL 命中外部直连库，路由到外部 MySQL 执行")
            result = await external_db.execute_external_sql(sql)
        else:
            # 获取数仓操作对象
            dw_mysql_repository = runtime.context["dw_mysql_repository"]
            # 执行sql
            result = await dw_mysql_repository.execute_sql(sql)

        # 输出执行结果
        logger.info(f"执行sql的结果{result}")
        # 解析处理结果
        writer({"result": result})
        # 结果写入 state，供下游洞察节点使用
        return {"result": result}
    except Exception as e:
        logger.error(f"执行sql的结果异常：{str(e)}")
        raise
