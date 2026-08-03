"""结合现有 AI Provider 与法律检索的结构化法律咨询服务。"""

from __future__ import annotations

from ai.llm_client import ProviderLLMClient
from legal_assistant.case_rag import CaseRAG
from legal_assistant.analysis_cache import AnalysisCache
from legal_assistant.legal_search_adapter import LegalKnowledgeSearch
from legal_assistant.reasoning_engine import LegalReasoningEngine, LegalReasoningError


class LegalAssistantError(RuntimeError):
    """法律咨询结果不满足结构要求。"""


class LegalAssistant:
    REQUIRED_FIELDS = (
        "question_analysis", "legal_basis", "risk_warnings", "recommended_actions",
        "dispute_issues", "evidence_recommendations", "uncertain_facts", "lawyer_review_notes",
        "facts", "case_type", "legal_relationships", "supplementary_questions", "lawyer_advice", "similar_cases",
        "legal_citation_validation",
        "case_match_explanations", "judgment_tendency", "lawyer_strategy_reference",
    )

    def __init__(self, *, llm_client=None, legal_search: LegalKnowledgeSearch | None = None, case_rag: CaseRAG | None = None, cache: AnalysisCache | None = None, use_cache: bool | None = None) -> None:
        self._llm_client = llm_client or ProviderLLMClient("deepseek")
        self._legal_search = legal_search or LegalKnowledgeSearch()
        self._case_rag = case_rag or CaseRAG()
        self._use_cache = (llm_client is None) if use_cache is None else use_cache
        self._cache = cache or AnalysisCache()

    def analyze(self, question: str, *, mode: str = "deep") -> dict:
        question = question.strip()
        if not question:
            raise LegalAssistantError("请输入需要分析的法律问题。")
        cache_payload = {"question": question, "mode": mode, "schema": "final-013-a-3-v1"}
        cached = self._cache.get("legal_consultation", cache_payload) if self._use_cache else None
        if cached is not None:
            cached["cache_hit"] = True
            return cached
        try:
            result = LegalReasoningEngine(llm_client=self._llm_client, legal_search=self._legal_search, case_rag=self._case_rag).analyze(question, mode=mode)
        except LegalReasoningError as exc:
            raise LegalAssistantError(str(exc)) from exc
        missing = [field for field in self.REQUIRED_FIELDS if field not in result]
        if missing:
            raise LegalAssistantError(f"法律分析缺少字段：{', '.join(missing)}")
        result["cache_hit"] = False
        if self._use_cache:
            self._cache.set("legal_consultation", cache_payload, result)
        return result
