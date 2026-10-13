from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def clarify(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """智能澄清节点：召回后没有任何可用表时，不再硬答，而是结合数仓现有表反问用户一句澄清问题。"""
    writer = runtime.stream_writer
    writer({"stage": "澄清问题"})
    try:
        query = state["query"]
        # 数仓现有表清单（供反问时给用户参考方向）
        meta_mysql_repository = runtime.context["meta_mysql_repository"]
        all_tables = await meta_mysql_repository.list_tables_with_description()

        prompt = PromptTemplate(
            template=loader_prompt("clarify"),
            input_variables=["query", "tables"],
        )
        chain = prompt | llm | StrOutputParser()
        text_out = (await chain.ainvoke({
            "query": query,
            "tables": "、".join(f"{t['name']}（{t['description']}）" for t in all_tables) or "暂无数据表",
        })).strip()
        logger.info(f"智能澄清：{text_out}")
        writer({"clarify": text_out})
        return {"clarify": text_out}
    except Exception as e:
        # 澄清失败也要给用户一个体面的回复
        logger.warning(f"澄清问题生成失败：{e}")
        writer({"clarify": "这个问题我没能对应到数仓里的数据，可以换个说法再试试，或者先看看数据字典里有哪些表。"})
        return {}
