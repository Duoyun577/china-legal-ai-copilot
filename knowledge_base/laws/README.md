# 法律

## 文件用途

存放现行法律、司法解释的结构化元数据与经核验的条文文本。

当前完整法律库包括：

- `civil_code_full.json`：中华人民共和国民法典，1260 条。
- `company_law.json`：中华人民共和国公司法（2023 年修订），266 条。
- `labor_contract_law.json`：中华人民共和国劳动合同法，98 条。
- `civil_procedure_law.json`：中华人民共和国民事诉讼法（2023 年修正），306 条。
- `civil_code_contract_interpretation.json`：民法典合同编通则司法解释，69 条。

`civil_code_contract.json` 继续作为合同审查场景的精选映射库保留，以兼容现有检索与规则引用。

## 数据格式

每部法律使用一个 UTF-8 JSON 数组文件，每条记录遵循 `knowledge_base/schema/law_schema.json`，并保留编、章、节层级和官方来源。

## 后续 RAG 接入方式

导入时按条文及其语义单元切分，保留法律名称、条号、生效状态、发布日期和来源链接等元数据。将文本与元数据向量化后写入检索库；问答阶段先以关键词和元数据过滤，再进行向量召回与原文引用。
