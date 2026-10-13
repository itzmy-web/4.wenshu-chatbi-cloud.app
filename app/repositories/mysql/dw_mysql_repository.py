# 云端版数仓仓储：SQLite 方言适配（原为 MySQL）
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 表名/字段名白名单：仅允许字母、数字、下划线（防 SQL 注入，table/column 名无法用参数绑定，只能拼接，必须先校验）
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str, kind: str = "标识符"):
    if not _IDENTIFIER_PATTERN.match(name):
        raise ValueError(f"非法的{kind}: {name!r}，仅允许字母、数字、下划线且不能以数字开头")


class DwMysqlRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_column_values(self, table_name: str, column_name: str, limit: int = 10):
        """查询指定字段的去重取值"""
        _validate_identifier(table_name, "表名")
        _validate_identifier(column_name, "字段名")
        sql = f"select distinct {column_name} from {table_name} limit {int(limit)}"
        result = await self.session.execute(text(sql))
        return result.scalars().fetchall()

    async def get_column_types(self, table_name: str):
        """查询表中字段的类型 {"字段名":"字段类型"}（SQLite: PRAGMA table_info）"""
        _validate_identifier(table_name, "表名")
        result = await self.session.execute(text(f"PRAGMA table_info({table_name})"))
        return {row.name: row.type for row in result.fetchall()}

    async def get_db_info(self):
        """查询数据库环境信息，版本、方言"""
        result = await self.session.execute(text("select sqlite_version()"))
        version = result.scalar()
        dialect = self.session.get_bind().dialect.name
        return {"version": version, "dialect": dialect}

    async def validate_sql(self, sql: str):
        """验证 SQL 语法（不合法会抛异常）"""
        await self.session.execute(text(f"explain {sql}"))

    async def execute_sql(self, sql):
        """执行最终 SQL，返回字典列表"""
        result = await self.session.execute(text(sql))
        return [dict(row) for row in result.mappings().fetchall()]
