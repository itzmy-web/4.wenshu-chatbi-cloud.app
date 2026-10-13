import asyncio
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.clients import external_db
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.prompt.prompt_loader import loader_prompt


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    # 获取流式输出器
    writer = runtime.stream_writer
    # 输出进度状态信息
    # writer("校验SQL")
    writer({"stage": "校验SQL"})
    # 获取生成sql
    sql = state["sql"]
    # 外部直连库的 SQL 不用本地 SQLite 校验（语法方言不同），跳过
    if external_db.is_external_sql(sql):
        logger.info("外部库 SQL，跳过本地语法校验")
        return {"error": None}
    # 获取数仓操作对象
    dw_mysql_repository = runtime.context["dw_mysql_repository"]
    # 捕获验证sql的异常信息
    try:
        # 执行验证sql
        await dw_mysql_repository.validate_sql(sql)
        # 无异常 None
        logger.info(f"sql验证正确：{sql}")
        return {"error": None}
    except Exception as e:
        logger.info(f"sql验证失败：{sql}")
        return {"error": str(e)}
