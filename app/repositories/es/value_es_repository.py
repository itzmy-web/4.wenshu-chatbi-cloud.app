# 云端版字段取值仓储：SQLite LIKE 检索替代 ES（取值数据量极小，完全够用）
import sqlite3

from app.core.paths import META_DB_PATH


def _connect():
    conn = sqlite3.connect(META_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class ValueEsRepository:
    """字段取值仓储（云端版）：接口与 ES 版一致，底层为 meta.db 的 value_info 表"""

    def __init__(self):
        pass

    async def search(self, keyword: str, threshold: float = 0.6, limit: int = 5) -> list[dict]:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT id, value, type, column_id, column_name, table_id, table_name "
                "FROM value_info WHERE value LIKE ? LIMIT ?",
                (f"%{keyword}%", limit),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    async def ensure_index(self):
        conn = _connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS value_info (
                    id TEXT PRIMARY KEY,
                    value TEXT,
                    type TEXT,
                    column_id TEXT,
                    column_name TEXT,
                    table_id TEXT,
                    table_name TEXT
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_value_info_value ON value_info(value)")
            conn.commit()
        finally:
            conn.close()

    async def upsert_values(self, value_infos: list, batch_size: int = 20):
        await self.ensure_index()
        conn = _connect()
        try:
            for v in value_infos:
                conn.execute(
                    "INSERT OR REPLACE INTO value_info(id, value, type, column_id, column_name, table_id, table_name) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (v["id"], v["value"], v["type"], v["column_id"], v["column_name"], v["table_id"], v["table_name"]),
                )
            conn.commit()
        finally:
            conn.close()
