# 云端版字段向量仓储：SQLite 存储稀疏向量，纯 Python 余弦检索
import json
import sqlite3

from app.core.paths import META_DB_PATH


def _connect():
    conn = sqlite3.connect(META_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b[t] for t, w in a.items() if t in b)


class ColumnQdrantRepository:
    """字段向量仓储（云端版）：接口与 Qdrant 版一致，底层为 meta.db 的 vectors 表"""

    collection_name: str = "column"

    def __init__(self):
        pass

    def _load_points(self) -> list[tuple[str, dict, dict]]:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT point_id, payload_json, vector_json FROM vectors WHERE collection=?",
                (self.collection_name,),
            ).fetchall()
        finally:
            conn.close()
        return [(r["point_id"], json.loads(r["payload_json"]), json.loads(r["vector_json"])) for r in rows]

    async def search(self, embedding: dict[str, float], score_threshold: float = 0.6, limit: int = 5) -> list[dict]:
        scored = [(payload, _cosine(embedding, vec)) for _, payload, vec in self._load_points()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [payload for payload, score in scored[:limit] if score >= score_threshold]

    async def ensure_collection(self):
        conn = _connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS vectors (
                    collection TEXT NOT NULL,
                    point_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    PRIMARY KEY (collection, point_id)
                )"""
            )
            conn.commit()
        finally:
            conn.close()

    async def upsert_column_embeddings(self, ids: list, embeddings: list, payloads: list, batch_size: int = 10):
        await self.ensure_collection()
        conn = _connect()
        try:
            for pid, vec, payload in zip(ids, embeddings, payloads):
                conn.execute(
                    "INSERT OR REPLACE INTO vectors(collection, point_id, payload_json, vector_json) VALUES (?,?,?,?)",
                    (self.collection_name, str(pid), json.dumps(payload, ensure_ascii=False), json.dumps(vec)),
                )
            conn.commit()
        finally:
            conn.close()
