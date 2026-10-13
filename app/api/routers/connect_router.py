# 数据库直连路由：POST /api/connect_db 连接外部 MySQL → 内省表结构 → 入 meta/向量 → 问数自动路由到外部库
import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends as DependsP
from pydantic import BaseModel
from sqlalchemy import text

from app.agent.llm import llm
from app.api.dependencies import get_meta_session
from app.api.routers.auth_router import verify_token
from app.api.routers.upload_router import _llm_table_meta
from app.clients import external_db
from app.clients.embedding_client_manager import embedding_client_manager
from app.core.log import logger
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL

connect_router = APIRouter()


class ConnectSchema(BaseModel):
    host: str
    port: int = 3306
    user: str
    password: str
    database: str


@connect_router.post("/api/connect_db")
async def connect_db(body: ConnectSchema,
                     _token: None = DependsP(verify_token),
                     meta_session=DependsP(get_meta_session)):
    config = body.model_dump()
    try:
        tables = await external_db.introspect_external(config)
    except Exception as e:
        logger.warning(f"外部数据库连接失败：{e}")
        raise HTTPException(status_code=400, detail=f"连接失败：{str(e)[:120]}")
    if not tables:
        raise HTTPException(status_code=400, detail="连接成功，但该库里没有数据表")

    db_sig = uuid.uuid5(uuid.NAMESPACE_DNS, f"{config['host']}:{config['port']}/{config['database']}").hex[:8]
    embedder = embedding_client_manager.client
    tables_meta = {}
    imported = []

    for tname, info in tables.items():
        tid = f"ext_{db_sig}_{tname[:40]}"
        cols = info["columns"]
        col_types = {c["name"]: ("number" if any(k in c["type"].lower() for k in ("int", "decimal", "double", "float")) else "text")
                     for c in cols}
        meta_gen = await _llm_table_meta(tname, cols, info["sample"])

        meta_session.add(TableInfoMySQL(id=tid, name=tname, role="fact", description=meta_gen["description"]))
        for c in cols:
            m = next(x for x in meta_gen["columns"] if x["name"] == c["name"])
            cid = f"{tname}.{c['name']}"
            sample_vals = [str(r.get(c["name"], "")) for r in info["sample"] if r.get(c["name"]) is not None][:5]
            meta_session.add(ColumnInfoMySQL(
                id=cid, name=c["name"], type=col_types[c["name"]],
                role="measure" if col_types[c["name"]] == "number" else "dimension",
                examples=sample_vals, description=m["description"], alias=m["alias"], table_id=tid))
            payload = {"id": cid, "name": c["name"], "type": col_types[c["name"]],
                       "role": "measure" if col_types[c["name"]] == "number" else "dimension",
                       "examples": sample_vals, "description": m["description"], "alias": m["alias"],
                       "table_id": tid}
            for t in [c["name"], m["description"]] + m["alias"]:
                if t:
                    vec = await embedder.aembed_query(t)
                    await meta_session.execute(text(
                        "INSERT OR REPLACE INTO vectors(collection, point_id, payload_json, vector_json) "
                        "VALUES ('column', :p, :pj, :vj)"),
                        {"p": uuid.uuid4().hex, "pj": json.dumps(payload, ensure_ascii=False),
                         "vj": json.dumps(vec)})
        tables_meta[tname] = {"id": tid, "columns": [c["name"] for c in cols]}
        imported.append({"table": tname, "columns": len(cols), "description": meta_gen["description"]})

    await meta_session.commit()
    external_db.connect_external(config, tables_meta)
    logger.info(f"外部数据库直连成功：{config['host']}/{config['database']}，导入 {len(imported)} 张表")
    return {"ok": True, "database": config["database"], "tables": imported}


@connect_router.post("/api/disconnect_db")
async def disconnect_db(_token: None = DependsP(verify_token)):
    external_db.disconnect_external()
    return {"ok": True}


@connect_router.get("/api/connect_db/status")
async def connect_status(_token: None = DependsP(verify_token)):
    ext = external_db.get_external()
    if not ext:
        return {"connected": False}
    return {"connected": True, "database": ext["config"]["database"],
            "host": ext["config"]["host"], "tables": list(ext["tables"].keys())}
