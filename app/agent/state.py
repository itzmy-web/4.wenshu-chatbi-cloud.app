from typing import TypedDict
from app.models.es.value_info_es import ValueInfoEs
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository


class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list[str]


class TableInfoStata(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


class MetricInfoStata(TypedDict):
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]


class DateInfoStata(TypedDict):
    date: str
    weekday: str
    quarter: str


class DBInfoStata(TypedDict):
    dialect: str
    version: str


class DataAgentState(TypedDict):
    query: str  # 用户的查询
    history: list[dict]  # 多轮追问的会话历史 [{question, sql, result_summary}]
    keywords: list[str]  # 提取关键字列表
    retrieved_columns: list[ColumnInfoQdrant]  # 召回列信息列表
    retrieved_values: list[ValueInfoEs]  # 召回值信息列表
    retrieved_metrics: list[MetricInfoQdrant]  # 召回指标信息列表
    table_infos: list[TableInfoStata]  # 封装表信息列表
    metric_infos: list[MetricInfoStata]  # 封装指标信息列表
    date_info: DateInfoStata  # 时间信息
    db_info: DBInfoStata  # 数据库环境信息
    sql: str
    result: list  # SQL 执行结果（行字典列表），供洞察节点使用
    insight: str  # AI 洞察一句话结论
    error: str  # 错误信息，根据state中是否存在错误信息，可以进行流程执行
    empty_retry_done: bool  # 空结果守卫：本次会话是否已回炉纠错过（防死循环）
    empty_retry_pending: bool  # 空结果守卫：本次执行结果为空且需要回炉纠错
