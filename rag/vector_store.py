"""向量存储抽象接口。

本阶段不连接任何向量数据库；具体实现可替换为本地或托管方案。
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence


@dataclass
class VectorRecord:
    """写入向量索引的一条法律知识记录。"""

    record_id: str
    text: str
    embedding: Sequence[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorSearchResult:
    """向量查询返回的候选记录与相关性分数。"""

    record: VectorRecord
    score: float


class VectorStore(Protocol):
    """供检索层依赖的最小向量存储契约。"""

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        """写入或更新索引记录。"""
        ...

    def search(
        self,
        query_embedding: Sequence[float],
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """按向量相似度和元数据过滤检索记录。"""
        ...


class InMemoryVectorStorePlaceholder:
    """占位实现，防止架构阶段意外触发真实数据库操作。"""

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        """TODO: 后续可用于本地开发的显式内存索引。"""
        raise NotImplementedError("No vector database is connected in the architecture phase.")

    def search(
        self,
        query_embedding: Sequence[float],
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """TODO: 接入向量数据库后执行相似度检索与元数据过滤。"""
        raise NotImplementedError("No vector database is connected in the architecture phase.")
