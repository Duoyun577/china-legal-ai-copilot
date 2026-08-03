# 司法解释

## 文件用途

存放最高人民法院、最高人民检察院发布的司法解释、司法政策性文件及相关适用说明的结构化资料。当前目录仅保留说明，不录入法律正文。

## 数据格式

建议采用 UTF-8 JSON 或 Markdown 文件，记录 `document_id`、`title`、`issuing_authority`、`document_number`、`promulgation_date`、`effective_date`、`related_laws`、`status`、`source_url`、`articles`。应标注废止、修正和适用范围。

## 后续 RAG 接入方式

以条文、解释要点和关联法条为基本切片单位，写入发布日期、效力状态、发布机关及关联法律等元数据。检索时优先过滤现行有效文件，并将召回内容与关联法律条文联合排序和展示。
