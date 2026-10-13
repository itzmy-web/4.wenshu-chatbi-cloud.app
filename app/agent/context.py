from typing import Any, TypedDict

from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class DataAgentContext(TypedDict):
    embedding_client: Any  # 词汇向量器（云端版内置，接口与原 HuggingFaceEndpointEmbeddings 对齐）
    column_qdrant_repository: ColumnQdrantRepository  # 字段向量库
    value_es_repository: ValueEsRepository  # 字段值索引库
    metric_qdrant_repository: MetricQdrantRepository  # 指标向量库
    meta_mysql_repository: MetaMysqlRepository  # 元数据库
    dw_mysql_repository: DwMysqlRepository  # 数据仓库
