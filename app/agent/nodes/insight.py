from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def insight(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """AI 洞察节点：基于用户问题与 SQL 执行结果生成一句话业务结论，SSE 推送前端。
    任何异常都静默降级（不影响主链路，前端只是少一条洞察）。"""
    writer = runtime.stream_writer
    writer({"stage": "AI 洞察"})
    try:
        query = state["query"]
        sql = state["sql"]
        result = state.get("result") or []

        # 截断结果，防止超长（最多取前 50 行 + 1500 字符）
        result_text = str(result)[:1500] if len(str(result)) <= 1500 else str(result[:50])[:1500]

        prompt = PromptTemplate(template=loader_prompt("insight"),
                                input_variables=["query", "sql", "result"])
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser
        text = (await chain.ainvoke({
            "query": query,
            "sql": sql,
            "result": result_text,
        })).strip()
        logger.info(f"AI 洞察：{text}")
        writer({"insight": text})
        return {"insight": text}
    except Exception as e:
        # 洞察属增强能力，失败静默跳过，不阻断主流程
        logger.warning(f"AI 洞察生成失败（已跳过）：{str(e)}")
        return {}
