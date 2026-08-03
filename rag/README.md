# Legal RAG 架构（第一阶段）

本目录定义 China Legal AI Copilot 的法律检索架构边界。当前仅包含接口、数据模型和 TODO，不连接真实数据库，也不调用外部 API。

## RAG 整体流程

```text
knowledge_base 法律数据
  → LegalDocumentLoader 加载与校验
  → 按法条/语义单元切分为 DocumentChunk
  → 嵌入模型生成向量（后续实现）
  → VectorStore 建立索引（后续实现）
  → LegalRetriever 过滤、召回与重排序
  → LegalSearchService 返回可引用法律依据
```

## 法律数据如何进入

法律、司法解释、案例、律师执业规则和模板将从 `knowledge_base/` 进入加载器。加载时应核验 UTF-8 编码、来源、发布日期、施行日期、效力状态、条号和文档类型。切分后必须保留这些元数据，特别是法律名称、章节、条号、`status`、`source_url` 和适用合同类型。

## Contract Review Agent 如何调用

`agents/contract_review/review_pipeline.yaml` 在“风险规则匹配”后，将命中的规则编号、风险描述与合同类型传入 `LegalSearchService.search_for_review`。该服务转换为 `RetrievalQuery`，由 `LegalRetriever` 优先利用规则关联和元数据过滤，再返回可追溯的法条或其他法律资料，供审查报告的“法律依据”部分引用。

## 后续接入向量数据库

实现一个符合 `VectorStore` 协议的适配器即可接入任意向量数据库。适配器应实现 `upsert` 和 `search`，支持向量相似度查询、`limit` 和元数据过滤。另行实现 `EmbeddingProvider` 生成文本向量，并在部署配置中注入具体实现；领域代码不应直接依赖数据库 SDK 或外部 API。

## 模块职责

- `document_loader.py`：法律文档加载、校验和切分。
- `vector_store.py`：向量记录与数据库无关的存储协议。
- `retriever.py`：检索请求、过滤、召回和结果模型。
- `legal_search.py`：Contract Review Agent 使用的法律检索服务门面。
