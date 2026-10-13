import asyncio
from os import name
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoStata, MetricInfoStata, ColumnInfoState, ValueInfoEs
from app.core.log import logger
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


async def merge_retrieved_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    # 获取流式输出器
    writer = runtime.stream_writer
    # 输出进度状态信息
    # writer("合并召回信息")
    writer({"stage": "合并召回信息"})
    try:
        # 封装表信息列表
        table_infos: list[TableInfoStata] = []
        # 封装指标信息列表
        metric_infos: list[MetricInfoStata] = []
        # 获取召回的字段列表
        retrieved_columns: list[ColumnInfoQdrant] = state["retrieved_columns"]
        # 获取召回的值列表
        retrieved_values: list[ValueInfoEs] = state["retrieved_values"]
        # 获取召回的指标信息
        retrieved_metrics: list[MetricInfoQdrant] = state["retrieved_metrics"]

        # 获取查询字段信息的mysql客户端对象
        meta_mysql_repository = runtime.context["meta_mysql_repository"]
        # 调整数据结构为字典，目的就是去重
        retrieved_columns_map: dict[str, ColumnInfoQdrant] = {retrieved_column["id"]: retrieved_column for
                                                              retrieved_column in retrieved_columns}

        # 1.处理召回的指标信息，将指标信息的相关字段加入到字段列表
        for retrieved_metric in retrieved_metrics:
            # 获取指标对应的字段列表（兼容 列id 与 "表.列名" 两种形式）
            relevant_columns = retrieved_metric["relevant_columns"]
            # 遍历字段列表
            for relevant_column in relevant_columns:
                # 判断列信息列表中是否已经在该字段
                if relevant_column in retrieved_columns_map:
                    continue
                # 先按字段id查询字段信息
                column_info_mysql: ColumnInfoMySQL | None = await meta_mysql_repository.get_column_info_by_id(
                    relevant_column)
                # 查不到且形如 "表.列名"，按表名+字段名解析
                if column_info_mysql is None and "." in str(relevant_column):
                    table_name, column_name = str(relevant_column).split(".", 1)
                    column_info_mysql = await meta_mysql_repository.get_column_info_by_table_and_name(
                        table_name, column_name)
                # 两种方式都解析不到，跳过该字段（不阻断主流程）
                if column_info_mysql is None:
                    logger.warning(f"指标关联字段无法解析，已跳过：{relevant_column}")
                    continue
                # 存储数据到retrieved_columns_map（以真实字段id为键，保证去重与后续取值回填）
                retrieved_columns_map[column_info_mysql.id] = convert_column_info_from_mysql_to_qdrant(
                    column_info_mysql)

        # 2.处理召回字段值列表，将值加入到列数据的example列表中
        # 遍历值列表
        for retrieved_value in retrieved_values:
            # 获取值
            column_value = retrieved_value["value"]
            # 获取列id
            column_id = retrieved_value["column_id"]
            # 如果值对应的列不存在，直接查询列存储到列map中
            if column_id not in retrieved_columns_map:
                # 当前对应的值所属的字段不在召回的字段列表中
                column_info_mysql = await meta_mysql_repository.get_column_info_by_id(column_id)
                # 查不到对应字段则跳过该取值（不阻断主流程）
                if column_info_mysql is None:
                    logger.warning(f"取值所属字段不存在，已跳过：column_id={column_id}, value={column_value}")
                    continue
                # 加入到列信息列表中
                retrieved_columns_map[column_id] = convert_column_info_from_mysql_to_qdrant(column_info_mysql)
            # 如果列对应的example 中不存在当前值，直接存储
            if column_value not in (retrieved_columns_map[column_id].get('examples') or []):
                # 当前值不存在example列表,添加到列表中
                retrieved_columns_map[column_id].setdefault('examples', []).append(column_value)

        # 3.将字段信息列表转换为表信息列表
        # 3.1 将字段信息分组，实现以表为单位进行归类 结构dict {table_id,list[ColumnInfoQdrant]}
        # 定义存储分组容器
        table_to_column_map: dict[str, list[ColumnInfoQdrant]] = {}
        # 遍历字段信息存储字典容器
        for column in retrieved_columns_map.values():
            # 从字段信息对象中获取表id
            table_id = column["table_id"]
            # 字段无所属表时跳过（防御脏数据）
            if table_id is None:
                logger.warning(f"字段缺少 table_id，已跳过：{column.get('id')}")
                continue
            # 如果指定的表id对应的数据不存在进行初始化
            if table_id not in table_to_column_map:
                table_to_column_map[table_id] = []
            # 存储遍历的字段信息到分组容器中
            table_to_column_map[table_id].append(column)

        # 显示的添加每个表的主外键字段
        for table_id in table_to_column_map.keys():
            # 根据表id，查询表的主外键字段
            key_columns: list[ColumnInfoMySQL] = await meta_mysql_repository.get_key_columns_by_table_id(table_id)
            # 获取当前table_id 对应字段id的列表
            column_ids = [column["id"] for column in table_to_column_map[table_id]]
            # 遍历查询的主外键列表
            for key_column in key_columns:
                # 判断当前主外键列是否存在当前表对应的字段列表中
                if key_column.id not in column_ids:
                    # 将当前表对应的主外键字段添加到字段列表中
                    table_to_column_map[table_id].append(convert_column_info_from_mysql_to_qdrant(key_column))

        # 3.2 table_id-->columns 转换为list[TableInfoStata]
        # 遍历字段分组容器
        for table_id, columns in table_to_column_map.items():
            # 根据表id查询表信息TableInfoMysql
            table: TableInfoMySQL | None = await meta_mysql_repository.get_table_info_by_id(table_id)
            # 表信息查不到则跳过（防御脏数据）
            if table is None:
                logger.warning(f"表信息不存在，已跳过：table_id={table_id}")
                continue
            # 转换字段数据 ColumnInfoQdrant-ColumnInfoStata
            columns = [convert_column_info_from_qdrant_to_stata(column) for column in columns]
            # 构建tableInfoStata
            table_info = TableInfoStata(
                name=table.name,
                role=table.role,
                description=table.description,
                columns=columns
            )
            # 收集组装的表数据
            table_infos.append(table_info)

        # 处理指标信息
        metric_infos = [convert_metric_info_from_qdrant_to_stata(retrieved_metric) for retrieved_metric in
                        retrieved_metrics]
        # 返回封装数据到后面节点
        return {"table_infos": table_infos, "metric_infos": metric_infos}

    except Exception as e:
        logger.error(f"合并召回信息异常:{str(e)}")
        raise


def convert_metric_info_from_qdrant_to_stata(metric_info_qdrant: MetricInfoQdrant) -> MetricInfoStata:
    """
    转换指标信息MetricInfoQdrant 为MetricInfoStata
    :param metric_info_qdrant:
    :return:
    """
    return MetricInfoStata(
        name=metric_info_qdrant['name'],
        description=metric_info_qdrant['description'],
        relevant_columns=metric_info_qdrant['relevant_columns'],
        alias=metric_info_qdrant['alias']

    )


def convert_column_info_from_qdrant_to_stata(column_info_qdrant: ColumnInfoQdrant) -> ColumnInfoState:
    """
    转化字段信息ColumnInfoQdrant 为ColumnInfoState
    :param column_info_qdrant:
    :return:
    """
    return ColumnInfoState(
        name=column_info_qdrant['name'],
        type=column_info_qdrant['type'],
        role=column_info_qdrant['role'],
        examples=column_info_qdrant['examples'],
        description=column_info_qdrant["description"],
        alias=column_info_qdrant['alias']

    )


# 定义转换类型的函数
def convert_column_info_from_mysql_to_qdrant(column_info_mysql: ColumnInfoMySQL) -> ColumnInfoQdrant:
    """
    转化字段信息ColumnInfoMySQL为ColumnInfoQdrant
    :param column_info_mysql:
    :return:
    """
    return ColumnInfoQdrant(
        id=column_info_mysql.id,
        name=column_info_mysql.name,
        type=column_info_mysql.type,
        role=column_info_mysql.role,
        examples=column_info_mysql.examples,
        description=column_info_mysql.description,
        alias=column_info_mysql.alias,
        table_id=column_info_mysql.table_id
    )
