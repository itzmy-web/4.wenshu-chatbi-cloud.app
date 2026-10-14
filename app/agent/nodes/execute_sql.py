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

        # 空结果守卫：SQL 语法正确但 0 行（常见于 WHERE 用了数据里不存在的取值、
        # JOIN 关联键写错、时间/条件范围超出数据区间）→ 回炉 correct_sql 纠错一次，
        # 避免把空表直接甩给用户。empty_retry_done 保证最多只回炉一次，不会死循环。
        if not result and not state.get("empty_retry_done"):
            hint = ("查询结果为空。SQL 语法正确但未命中任何数据，常见原因："
                    "WHERE 里使用了数据中不存在的取值（例如把‘大区名’当成了具体省份值）、"
                    "JOIN 关联键写错、或时间/条件范围超出数据区间。"
                    "请复核筛选条件，用数据里真实存在的取值重新生成 SQL；"
                    "若条件本身合法，改为返回聚合值为 0 的查询。")
            logger.info("执行结果为空，触发一次回炉纠错（空结果守卫）")
            return {"result": result, "error": hint,
                    "empty_retry_done": True, "empty_retry_pending": True}

        # 结果写入 state，供下游洞察节点使用
        return {"result": result, "empty_retry_pending": False}
    except Exception as e:
        logger.error(f"执行sql的结果异常：{str(e)}")
        raise
