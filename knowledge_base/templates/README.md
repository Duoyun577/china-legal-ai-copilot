# 法律文书模板

## 文件用途

存放合同、函件、法律意见书、合规清单及其他法律文书模板的元数据、条款模块和使用说明。当前目录仅保留说明，不录入模板正文。

## 数据格式

建议模板正文采用 Markdown 或 DOCX，并配套 UTF-8 JSON 元数据。元数据建议包含 `template_id`、`title`、`document_type`、`jurisdiction`、`applicable_scenarios`、`variables`、`clauses`、`version`、`last_reviewed_at`、`source`。变量使用统一占位符，例如 `{{party_a_name}}`。

## 后续 RAG 接入方式

将模板按条款模块切分，并为每段标注适用场景、可选变量、风险标签和版本。生成阶段先检索匹配的条款模块，再结合用户事实填充变量；输出必须保留模板版本、来源与人工复核提示。
