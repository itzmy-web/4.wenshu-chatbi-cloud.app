import json

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState


class QueryService:
    def __init__(self,
                 embedding_client,
                 column_qdrant_repository,
                 value_es_repository,
                 metric_qdrant_repository,
                 meta_mysql_repository,
                 dw_mysql_repository):

        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.value_es_repository = value_es_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository

    async def query(self, query: str, history: list[dict] | None = None):
        """
        用户查询的业务处理
        :param query: 用户当前这轮的查询
        :param history: 近几轮会话历史 [{question, sql, result_summary}]，用于多轮追问
        """
        # 创建上下文对象
        context = DataAgentContext(
            embedding_client=self.embedding_client,
            column_qdrant_repository=self.column_qdrant_repository,
            value_es_repository=self.value_es_repository,
            metric_qdrant_repository=self.metric_qdrant_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository
        )
        # 创建状态对象（携带会话历史，供生成 SQL 时解析指代与省略）
        state = DataAgentState(query=query, history=history or [])
        try:
            # 调用图流式输出
            async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
                yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False, default=str)}\n\n"
