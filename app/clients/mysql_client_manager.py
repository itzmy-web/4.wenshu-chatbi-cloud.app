import asyncio
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker

from app.core.paths import META_DB_PATH, DW_DB_PATH


class MysqlClientManager:
    """SQLite 异步客户端管理器（云端版）：meta.db 与 dw.db 随应用携带"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.engine: Optional[AsyncEngine] = None
        self.session_factory = None

    def _get_url(self):
        return f"sqlite+aiosqlite:///{self.db_path.as_posix()}"

    def init(self):
        self.engine = create_async_engine(url=self._get_url())
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=True,
            autobegin=True,
            expire_on_commit=False,
        )

    async def close(self):
        if self.engine is not None:
            await self.engine.dispose()


# 数仓库客户端（dw.db）
dw_mysql_client_manager = MysqlClientManager(DW_DB_PATH)
# 元数据库客户端（meta.db）
meta_mysql_client_manager = MysqlClientManager(META_DB_PATH)
