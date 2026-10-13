import json
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.core.paths import META_DB_PATH


def _load_idf() -> dict[str, float]:
    """从 meta.db 加载词汇向量的 idf 统计"""
    conn = sqlite3.connect(META_DB_PATH)
    try:
        row = conn.execute("SELECT json FROM vector_meta WHERE key='idf'").fetchone()
        return json.loads(row[0]) if row else {}
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化客户端：SQLite 引擎 + 内置词汇向量器
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    embedding_client_manager.init_with_client(
        __import__("app.clients.embedding_client_manager", fromlist=["LexicalEmbedder"]).LexicalEmbedder(_load_idf())
    )
    yield
    # 释放资源
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
