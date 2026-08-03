"""法律知识文档加载与规范化的架构接口。

本阶段不读取外部服务、不建立索引，只定义后续实现所需的数据模型和边界。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class LegalDocument:
    """进入 RAG 管道前的标准化法律文档。"""

    document_id: str
    title: str
    content: str
    source_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentChunk:
    """用于嵌入与检索的文档切片。"""

    chunk_id: str
    document_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class LegalDocumentLoader:
    """加载 knowledge_base 中的 JSON、Markdown 和后续支持的文档格式。"""

    def load(self, source_path: Path) -> Iterable[LegalDocument]:
        """返回指定路径下的标准化法律文档。

        TODO: 按文件扩展名分发 JSON、Markdown、DOCX 和 PDF 解析器。
        TODO: 校验法律名称、条号、效力状态、来源链接等必填元数据。
        TODO: 记录加载错误与数据版本，支持增量加载。
        """
        raise NotImplementedError("Document loading is planned for a later phase.")

    def chunk(self, document: LegalDocument) -> list[DocumentChunk]:
        """将法律文档按条、款、项或语义单元切分。

        TODO: 为法律、司法解释、案例和模板分别配置切分策略。
        TODO: 保留条号、章节、效力状态与来源等可过滤元数据。
        TODO: 支持重叠窗口和长条文的层级化切分。
        """
        raise NotImplementedError("Document chunking is planned for a later phase.")
