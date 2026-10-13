import math
import re
from collections import Counter
from typing import Optional


def _tokenize(text: str) -> Counter:
    """中文友好的字符 1+2 gram 分词，返回词频 Counter"""
    text = re.sub(r"\s+", "", str(text).lower())
    tokens: list[str] = []
    for ch in text:
        tokens.append(ch)
    for i in range(len(text) - 1):
        tokens.append(text[i:i + 2])
    return Counter(tokens)


class LexicalEmbedder:
    """
    内置词汇向量器：char-ngram TF-IDF 稀疏向量（dict[token, weight]）。
    与原 Qdrant 版接口对齐：aembed_query / aembed_documents。
    零外部依赖，适合沙箱化部署；语料统计（idf）由迁移脚本写入 meta.db。
    """

    def __init__(self, idf: Optional[dict[str, float]] = None):
        # idf 为空时使用统一权重（退化但仍可做重叠度匹配）
        self.idf = idf or {}

    def _weight(self, token: str) -> float:
        return self.idf.get(token, 1.0)

    def embed(self, text: str) -> dict[str, float]:
        tf = _tokenize(text)
        vec = {t: (1 + math.log(c)) * self._weight(t) for t, c in tf.items()}
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
        return {t: w / norm for t, w in vec.items()}

    async def aembed_query(self, text: str) -> dict[str, float]:
        return self.embed(text)

    async def aembed_documents(self, texts: list[str]) -> list[dict[str, float]]:
        return [self.embed(t) for t in texts]


class EmbeddingClientManager:
    """云端版向量客户端管理器：内置词汇向量，无需外部 embedding 服务"""

    def __init__(self):
        self.client: Optional[LexicalEmbedder] = None

    def init_with_client(self, client: LexicalEmbedder):
        self.client = client


embedding_client_manager = EmbeddingClientManager()
