"""法律检索编排层的架构接口。"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from vector_store import VectorSearchResult, VectorStore


@dataclass
class RetrievalQuery:
    """由 Agent 发起的、带法律语境的检索请求。"""

    query: str
    contract_type: str | None = None
    risk_rule_ids: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    limit: int = 5


@dataclass
class RetrievalResponse:
    """检索结果及其可追溯的筛选信息。"""

    results: list[VectorSearchResult]
    applied_filters: dict[str, Any]
    notes: list[str] = field(default_factory=list)


class EmbeddingProvider(Protocol):
    """文本嵌入能力的抽象；实现层可在后续替换。"""

    def embed(self, text: str) -> list[float]:
        """将文本转换为向量。"""
        ...


class LegalRetriever:
    """执行规则关联、元数据过滤和向量召回的法律检索器。"""

    def __init__(self, vector_store: VectorStore, embedding_provider: EmbeddingProvider) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider

    def retrieve(self, request: RetrievalQuery) -> RetrievalResponse:
        """检索与审查风险相关的法律依据。

        TODO: 将 risk_rule_ids 映射为法律主题、条号和关键词。
        TODO: 默认过滤“现行有效”法律，并支持合同类型和文件层级过滤。
        TODO: 融合关键词召回、向量召回、重排序及去重。
        TODO: 生成带来源、条号、效力状态的可引用结果。
        """
        raise NotImplementedError("Legal retrieval is planned for a later phase.")
