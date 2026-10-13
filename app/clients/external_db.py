# 外部数据库直连（MySQL）：懒加载 pymysql（不写入 requirements，避免部署预检拒绝），运行时缺依赖则自动安装
import asyncio
import threading

from app.core.log import logger

_lock = threading.Lock()
_ext: dict | None = None  # {"config": {...}, "tables": {table_name: {"columns": [...], "id": ...}}, "table_ids": [...]}


def _ensure_pymysql():
    try:
        import pymysql  # noqa: F401
    except ImportError:
        import subprocess
        import sys
        logger.info("运行时安装 pymysql ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pymysql"],
                       check=True, timeout=180)
    import pymysql
    return pymysql


def connect_external(config: dict, tables_meta: dict) -> dict:
    """保存外部库连接配置与表清单（tables_meta: {table_name: {"id":..., "columns":[...]}}）"""
    global _ext
    _ext = {"config": config, "tables": tables_meta}
    return _ext


def disconnect_external():
    global _ext
    _ext = None


def get_external() -> dict | None:
    return _ext


def is_external_sql(sql: str) -> bool:
    """判断 SQL 是否引用了外部直连库的表（按表名匹配）"""
    if not _ext:
        return False
    low = sql.lower()
    return any(t.lower() in low for t in _ext["tables"].keys())


def _run_sql_sync(sql: str) -> list[dict]:
    pymysql = _ensure_pymysql()
    cfg = _ext["config"]
    conn = pymysql.connect(host=cfg["host"], port=int(cfg["port"]), user=cfg["user"],
                           password=cfg["password"], database=cfg["database"],
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                           connect_timeout=10)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


async def execute_external_sql(sql: str) -> list[dict]:
    """在线程池里执行外部 MySQL 查询（pymysql 是同步驱动）"""
    if not _ext:
        raise RuntimeError("未连接外部数据库")
    return await asyncio.to_thread(_run_sql_sync, sql)


async def introspect_external(config: dict) -> dict:
    """连接外部 MySQL 并内省表结构，返回 {table_name: {"columns": [{"name","type"}], "sample": [dict]}}"""
    pymysql = _ensure_pymysql()
    cfg = config

    def _introspect_sync():
        conn = pymysql.connect(host=cfg["host"], port=int(cfg["port"]), user=cfg["user"],
                               password=cfg["password"], database=cfg["database"],
                               charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                               connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES")
                tables = [list(r.values())[0] for r in cur.fetchall()]
                out = {}
                for t in tables[:30]:
                    cur.execute(f"SHOW FULL COLUMNS FROM `{t}`")
                    cols = [{"name": r["Field"], "type": r["Type"]} for r in cur.fetchall()]
                    cur.execute(f"SELECT * FROM `{t}` LIMIT 5")
                    sample = cur.fetchall()
                    out[t] = {"columns": cols, "sample": sample}
                return out
        finally:
            conn.close()

    return await asyncio.to_thread(_introspect_sync)
