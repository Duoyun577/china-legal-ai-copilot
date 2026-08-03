"""根据合同法律审查意见书模板生成 Markdown 报告。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from contract_review_service import ContractReviewResult
from legal_assistant.citation_utils import risk_citations


class ReportService:
    """读取 Markdown 模板并渲染离线审查报告。"""

    def __init__(self, template_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self._template_path = template_path or project_root / "document" / "templates" / "contract_review_report.md"

    def generate(self, review: ContractReviewResult) -> str:
        """将结构化审查结果填充到合同法律审查意见书模板。

        TODO: 使用模板引擎支持循环、条件区块和律师自定义结论。
        TODO: 接入 LLM 生成条款级修改建议草案，并保留人工审核节点。
        TODO: 支持 DOCX/PDF 报告导出与引用编号。
        """
        template = self._template_path.read_text(encoding="utf-8")
        counts = {level: sum(risk.risk_level == level for risk in review.risks) for level in ("HIGH", "MIDDLE", "LOW")}
        risk_rows = self._risk_rows(review)
        basis_sections = self._basis_sections(review)
        suggestion_sections = self._suggestion_sections(review)
        replacements = {
            "{{report_id}}": f"CR-{date.today():%Y%m%d}",
            "{{report_date}}": date.today().isoformat(),
            "{{review_status}}": "离线规则初审（待律师复核）",
            "{{contract_name}}": review.contract_path.name,
            "{{contract_type}}": review.contract_type,
            "{{client_name}}": "待填写",
            "{{counterparty_name}}": "待填写",
            "{{contract_version}}": "待填写",
            "{{review_scope}}": "离线规则与本地法律依据初审",
            "{{overall_risk_level}}": self._overall_level(review),
            "{{high_risk_count}}": str(counts["HIGH"]),
            "{{middle_risk_count}}": str(counts["MIDDLE"]),
            "{{low_risk_count}}": str(counts["LOW"]),
            "{{lawyer_summary}}": "本报告由离线关键词规则生成，已识别的高风险事项应在签署前优先处理，并由执业律师结合完整事实与交易背景复核。",
            "{{next_action_1}}": "优先修订 HIGH 风险条款并形成书面谈判记录。",
            "{{next_action_2}}": "补充验收、付款、知识产权和争议解决的可执行条款。",
            "{{next_action_3}}": "由律师复核风险定位、法律依据与最终文本。",
        }
        for placeholder, value in replacements.items():
            template = template.replace(placeholder, value)
        template = template.replace("| 1 | {{risk_name}} | {{risk_level}} | {{clause_reference}} | {{risk_description}} |", risk_rows)
        template = self._replace_section(template, "## 四、法律依据", "## 五、修改建议", basis_sections)
        template = self._replace_section(template, "## 五、修改建议", "## 六、律师总结意见", suggestion_sections)
        return template

    @staticmethod
    def _risk_rows(review: ContractReviewResult) -> str:
        if not review.risks:
            return "| - | 未发现规则命中 | LOW | - | 当前离线规则未匹配到风险；仍建议人工复核。 |"
        return "\n".join(
            f"| {index} | {risk.name}（{risk.rule_id}） | {risk.risk_level} | 全文关键词匹配 | 命中：{', '.join(risk.matched_keywords)}；{risk.legal_issue} |"
            for index, risk in enumerate(review.risks, start=1)
        )

    @staticmethod
    def _basis_sections(review: ContractReviewResult) -> str:
        sections: list[str] = []
        for index, risk in enumerate(review.risks, start=1):
            bases = review.legal_basis_by_rule.get(risk.rule_id, [])
            citations = "\n".join(
                f"- 法律依据：{item['legal_basis']}\n  - 法律名称：{item['law_name']}\n  - 条文编号：{item['article']}\n"
                f"  - 条文内容：{item['legal_text']}\n  - 来源文件：{item['source_file']}\n  - 官方来源：{item['source']}"
                for item in risk_citations(risk, bases)
            )
            sections.append(f"### 风险 {index}：{risk.name}\n\n{citations}")
        return "\n\n".join(sections)

    @staticmethod
    def _suggestion_sections(review: ContractReviewResult) -> str:
        return "\n\n".join(
            f"### 风险 {index}：{risk.name}\n\n- 修改目标：降低{risk.category}。\n- 建议条款或修改方向：{risk.suggestion}\n- 谈判优先级：{risk.risk_level}\n- 未采纳建议时的履行控制措施：保留书面沟通、验收及付款凭证，并安排律师复核。"
            for index, risk in enumerate(review.risks, start=1)
        )

    @staticmethod
    def _overall_level(review: ContractReviewResult) -> str:
        if any(risk.risk_level == "HIGH" for risk in review.risks):
            return "HIGH"
        if any(risk.risk_level == "MIDDLE" for risk in review.risks):
            return "MIDDLE"
        return "LOW"

    @staticmethod
    def _replace_section(document: str, start: str, end: str, content: str) -> str:
        start_index = document.index(start) + len(start)
        end_index = document.index(end)
        return document[:start_index] + "\n\n" + content + "\n\n" + document[end_index:]
