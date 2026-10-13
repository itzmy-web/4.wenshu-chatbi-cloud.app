# 数据字典路由：GET /api/dictionary 返回数仓所有表与字段的完整信息
import json

from fastapi import APIRouter, Depends
from fastapi.params import Depends as DependsP
from sqlalchemy import text

from app.api.dependencies import get_meta_session
from app.api.routers.auth_router import verify_token

dictionary_router = APIRouter()


@dictionary_router.get("/api/dictionary")
async def dictionary(_token: None = DependsP(verify_token), meta_session=DependsP(get_meta_session)):
    """数据字典：列出所有表（含用户上传的），每张表的字段、类型、描述、别名、示例值"""
    tables = (await meta_session.execute(text(
        "SELECT id, name, role, description FROM table_info ORDER BY id"))).fetchall()
    columns = (await meta_session.execute(text(
        "SELECT name, type, role, examples, description, alias, table_id FROM column_info ORDER BY table_id, id"))).fetchall()
    col_counts = (await meta_session.execute(text(
        "SELECT table_id, COUNT(*) FROM column_info GROUP BY table_id"))).fetchall()

    from collections import defaultdict
    cols_by_table: dict[str, list] = defaultdict(list)
    for name, ctype, role, examples, description, alias, table_id in columns:
        try:
            ex = json.loads(examples) if isinstance(examples, str) else (examples or [])
        except Exception:
            ex = []
        try:
            al = json.loads(alias) if isinstance(alias, str) else (alias or [])
        except Exception:
            al = []
        cols_by_table[table_id].append({
            "name": name, "type": ctype, "role": role,
            "examples": ex[:5], "description": description, "alias": al,
        })

    out = []
    for tid, tname, trole, tdesc in tables:
        out.append({"id": tid, "name": tname, "role": trole, "description": tdesc,
                    "columns": cols_by_table.get(tid, [])})
    return {"tables": out}
