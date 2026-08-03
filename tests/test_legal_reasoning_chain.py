import json

import pytest

from ai.llm_client import LLMResponse
from legal_assistant.assistant import LegalAssistant, LegalAssistantError
from legal_assistant.case_issue_analyzer import CaseIssueAnalyzer
from legal_assistant.legal_search_adapter import LegalCitation
from legal_assistant.reasoning_engine import LegalReasoningEngine


class CapturingSearch:
    def __init__(self, results=None):
        self.query = ""
        self.results = results if results is not None else [
            LegalCitation("中华人民共和国民法典", "第五百七十七条", "不履行合同义务的，应承担违约责任。", "国家法律法规数据库", "《中华人民共和国民法典》第五百七十七条", 4.0)
        ]

    def search(self, question, *, top_k=5):
        self.query = question
        return self.results


class ChainLLM:
    def complete(self, messages, *, response_format="text"):
        payload = {
            "risk_warnings": ["证据及诉讼时效风险待核实"],
            "lawyer_advice": ["先书面催告并固定证据"],
            "question_analysis": "对方可能构成违约。",
            "recommended_actions": ["发送催告函"],
            "evidence_recommendations": ["合同和付款凭证"],
            "uncertain_facts": ["履行期限"],
            "lawyer_review_notes": ["律师复核"],
        }
        return LLMResponse(json.dumps(payload, ensure_ascii=False), "test", True)


def test_case_issue_analyzer_builds_pre_retrieval_case_profile():
    result = CaseIssueAnalyzer().analyze("双方签订买卖合同，对方逾期未付货款。")

    assert result.case_type == "买卖合同纠纷"
    assert result.facts
    assert result.legal_relationships
    assert "各方是否按约履行及是否构成违约" in result.dispute_issues
    assert result.supplementary_questions


def test_reasoning_engine_runs_all_stages_and_keeps_verified_citations():
    search = CapturingSearch()
    result = LegalReasoningEngine(llm_client=ChainLLM(), legal_search=search).analyze("合同到期未付款怎么办？")

    assert result["reasoning_stages"] == list(LegalReasoningEngine.STAGES)
    assert result["case_type"] == "合同纠纷"
    assert "合同纠纷" in search.query
    assert result["legal_basis"][0]["article"] == "第五百七十七条"
    assert result["lawyer_advice"] == ["先书面催告并固定证据"]
    assert result["case_match_explanations"]
    assert result["judgment_tendency"]
    assert result["lawyer_strategy_reference"]


def test_legal_assistant_reports_empty_legal_search_result():
    with pytest.raises(LegalAssistantError, match="未检索到"):
        LegalAssistant(llm_client=ChainLLM(), legal_search=CapturingSearch([])).analyze("陌生法律事项")
