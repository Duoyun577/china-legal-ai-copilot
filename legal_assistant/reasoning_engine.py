"""法律咨询案件分析推理链的编排层。"""

from __future__ import annotations

from legal_assistant.case_issue_analyzer import CaseIssueAnalyzer
from legal_assistant.case_rag import CaseRAG
from legal_assistant.citation_utils import citation_dict
from legal_assistant.legal_advisor_chain import LegalAdvisorChain, LegalAdvisorChainError
from legal_assistant.legal_reference_validator import LegalReferenceValidator


class LegalReasoningError(RuntimeError):
    """案件推理链无法完成。"""


class LegalReasoningEngine:
    STAGES = (
        "fact_extraction", "case_type_classification", "legal_relationship_analysis",
        "dispute_issue_identification", "supplementary_questions", "legal_basis_retrieval", "similar_case_retrieval",
        "risk_warnings", "lawyer_advice",
    )

    def __init__(self, *, llm_client, legal_search, case_rag=None, issue_analyzer=None, advisor_chain=None) -> None:
        self._legal_search = legal_search
        self._case_rag = case_rag or CaseRAG()
        self._issue_analyzer = issue_analyzer or CaseIssueAnalyzer()
        self._advisor_chain = advisor_chain or LegalAdvisorChain(llm_client)

    def analyze(self, question: str, *, mode: str = "deep") -> dict:
        if mode not in {"quick", "deep"}:
            raise LegalReasoningError("咨询模式必须为 quick 或 deep。")
        issue = self._issue_analyzer.analyze(question)
        issue_data = issue.as_dict()
        retrieval_query = " ".join([question, issue.case_type, *issue.legal_relationships, *issue.dispute_issues])
        citations = self._legal_search.search(retrieval_query, top_k=5)
        if not citations:
            raise LegalReasoningError("本地法律知识库未检索到可核验法条，请补充问题关键词后重试。")
        legal_basis = [citation_dict(item) for item in citations]
        citation_validation = LegalReferenceValidator().validate_many(legal_basis)
        similar_cases = [item.as_dict() for item in self._case_rag.search(retrieval_query, case_type=issue.case_type, top_k=3)]
        if mode == "quick":
            result = self._quick_result(issue_data, legal_basis, similar_cases)
        else:
            try:
                result = self._advisor_chain.advise(question, issue_data, legal_basis, similar_cases)
            except LegalAdvisorChainError as exc:
                raise LegalReasoningError(str(exc)) from exc

        result.update(issue_data)
        result["legal_basis"] = legal_basis
        result["legal_citation_validation"] = citation_validation
        # 类案字段以本地案例库为准，防止模型编造案名、法院或裁判观点。
        result["similar_cases"] = similar_cases
        result["case_match_explanations"] = [
            {"case_name": item["case_name"], "similarities": item["similarity_analysis"]}
            for item in similar_cases
        ]
        result["judgment_tendency"] = [item["judgment_trend"] for item in similar_cases] or ["暂无足够类案形成裁判倾向判断"]
        result["lawyer_strategy_reference"] = list(dict.fromkeys(
            strategy for item in similar_cases for strategy in item["lawyer_strategy"]
        )) or ["结合案件事实、证据与最新司法实践由承办律师制定策略"]
        result.setdefault("question_analysis", f"初步判断为{issue.case_type}，需结合补充事实和证据进一步分析。")
        result.setdefault("recommended_actions", list(result["lawyer_advice"]))
        result.setdefault("evidence_recommendations", ["保存并按时间顺序整理合同、沟通、付款及履行凭证"])
        result.setdefault("lawyer_review_notes", ["由执业律师结合原始证据、时效及管辖情况复核"])
        result["reasoning_stages"] = list(self.STAGES)
        result["analysis_mode"] = mode
        return result

    @staticmethod
    def _quick_result(issue_data: dict, legal_basis: list[dict], similar_cases: list[dict]) -> dict:
        advice = ["先补齐关键事实和证据，再由律师结合请求目标确定交涉或诉讼方案"]
        return {
            **issue_data,
            "question_analysis": f"快速初筛：初步归类为{issue_data['case_type']}。",
            "legal_basis": legal_basis,
            "similar_cases": similar_cases,
            "case_match_explanations": [],
            "judgment_tendency": [],
            "lawyer_strategy_reference": [],
            "risk_warnings": ["快速模式未进行模型深度论证；时效、管辖、举证及执行风险均需律师复核"],
            "lawyer_advice": advice,
            "recommended_actions": advice,
            "evidence_recommendations": ["按时间顺序整理合同、沟通记录、付款凭证及履行材料"],
            "lawyer_review_notes": ["建议切换深度律师模式形成完整分析，最终意见以承办律师确认为准"],
        }
