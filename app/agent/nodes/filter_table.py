import asyncio
import copy
import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from sqlalchemy import true

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, TableInfoStata
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    # 获取流式输出器
    writer = runtime.stream_writer
    # 输出进度状态信息
    # writer("过滤表")
    writer({"stage": "过滤表"})
    try:

        # 获取用户查询
        query = state["query"]
        # 获取合并后的表数据
        table_infos: list[TableInfoStata] = state["table_infos"]

        # 2026-10-14 兜底修复：先留一份「召回原件」快照。
        # 背景：纯指标问法（如"今年的总GMV是多少"）在过滤表这步 LLM 偶尔返回空，
        # 导致表为空 → 触发澄清反问（昨天能出数、今天反问你），属间歇性退化。
        # 修复：过滤后若表为空或结构非法，回退到召回原件，保证行为确定化。
        recalled_tables = copy.deepcopy(table_infos)

        # 1.使用LLM对组合的表和字段数据根据需求过滤
        # 定义提示词
        prompt = PromptTemplate(template=loader_prompt("filter_table_info"), input_variables=["query", "table_infos"])
        # 定义json格式化输出对象
        output_parser = JsonOutputParser()
        # 组合chain链
        chain = prompt | llm | output_parser
        # 执行chain
        result = await chain.ainvoke(
            {
                "query": query,
                "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False) # yaml.dump(...)  →  转成 YAML 文本字符串
            }
        )
        # https://pyyaml.org/wiki/PyYAMLDocumentation
        # print(f"json转换的结果{yaml.dump(table_infos)}")

        """
         {
         "表名1":["字段1", "字段2", "..."],
         "表名2":["字段1", "字段2", "..."]
        }


        """
        # 2026-10-14：LLM 返回结构非法（非 dict）时视为过滤失败，直接走兜底
        if not isinstance(result, dict):
            logger.warning(f"过滤表返回结构非法（{type(result).__name__}），回退全量召回结果")
            result = {}

        # 2.根据大模型返回根据业务相关的表和列调整table_infos
        # 2.1判断过滤掉大模型返回与业务无关的表和字段 浅拷贝
        for table_info in table_infos[:]:
            # 如果不存在过滤的结果，移除表数据
            if table_info["name"] not in result:
                # 移除表数据
                table_infos.remove(table_info)
            else:
                # 如果存在过滤的结果中， 处理表字段
                # 获取返回指定表的字段列表
                selected_columns = result[table_info["name"]]
                # 2026-10-14：字段列表非法时保留该表原字段（不做裁剪），避免表被"选空"
                if not isinstance(selected_columns, (list, tuple, set)):
                    logger.warning(f"过滤表返回字段结构非法：表={table_info['name']}，保留原字段")
                    continue
                # 遍历组合的字段列表  浅拷贝
                for column in table_info["columns"][:]:
                    # 判断是否存在返回的结果中
                    if column["name"] not in selected_columns:
                        table_info["columns"].remove(column)

        # 2026-10-14 兜底：过滤后没有可用表，或某表字段被裁空 → 回退召回原件
        if not table_infos:
            logger.warning("过滤表结果为空，回退全量召回结果（避免误触发澄清反问）")
            table_infos = recalled_tables
        else:
            empty_tables = [t["name"] for t in table_infos if not t["columns"]]
            if empty_tables:
                logger.warning(f"以下表字段被裁空，回退其召回字段：{empty_tables}")
                recalled_map = {t["name"]: t for t in recalled_tables}
                for table_info in table_infos:
                    if not table_info["columns"] and table_info["name"] in recalled_map:
                        table_info["columns"] = recalled_map[table_info["name"]]["columns"]

        logger.info(f"过滤后的表信息{[table_info['name'] for table_info in table_infos]}")
        # 把命中的表与字段推给前端（展示在执行过程详情中）
        writer({"tables": [{"table": t["name"], "columns": [c["name"] for c in t["columns"]]}
                           for t in table_infos]})
        # 结果不符合要求（5。如果选择了多张表，需要确保所选字段包含join所需的主外键）
        return {"table_infos": table_infos}
    except Exception as e:
        logger.error(f"过滤后的表信息异常：{str(e)}")
        raise


# ========== 简单测试 ==========
