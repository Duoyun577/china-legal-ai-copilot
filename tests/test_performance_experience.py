import json

from ai.llm_client import LLMResponse
from case_manager import CaseManager
from case_manager.workflow import CaseWorkflow
from legal_assistant.analysis_cache import AnalysisCache
from legal_assistant.assistant import LegalAssistant
from legal_assistant.case_analysis_report import CaseLegalAnalysisReportGenerator
from legal_assistant.legal_search_adapter import LegalCitation
from lawyer_memory import LawyerMemory


class CountingLLM:
    def __init__(self):
        self.calls = 0

    def complete(self, messages, *, response_format="text"):
        self.calls += 1
        payload = {
            "question_analysis": "可能构成违约。",
            "legal_basis": [],
            "risk_warnings": ["证据待核实"],
            "recommended_actions": ["书面催告"],
            "lawyer_advice": ["书面催告"],
            "dispute_issues": ["付款是否届期"],
            "evidence_recommendations": ["核对合同"],
            "uncertain_facts": ["付款日期"],
            "lawyer_review_notes": ["律师复核"],
        }
        return LLMResponse(json.dumps(payload, ensure_ascii=False), "test", True)


class FakeLegalSearch:
    def search(self, question, *, top_k=5):
        return [LegalCitation(
            "中华人民共和国民法典", "第五百七十七条", "不履行合同义务的，应承担违约责任。",
            "国家法律法规数据库", "《中华人民共和国民法典》第五百七十七条", 9.0,
            "knowledge_base/laws/civil_code_full.json",
        )]


def test_repeated_deep_consultation_uses_single_llm_call(tmp_path):
    client = CountingLLM()
    cache = AnalysisCache(tmp_path / "consultation-cache.db")
    assistant = LegalAssistant(llm_client=client, legal_search=FakeLegalSearch(), cache=cache, use_cache=True)

    first = assistant.analyze("合同到期未付款怎么办？", mode="deep")
    second = assistant.analyze("合同到期未付款怎么办？", mode="deep")

    assert client.calls == 1
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["question_analysis"] == first["question_analysis"]


def test_quick_consultation_uses_no_llm_and_keeps_output_schema(tmp_path):
    client = CountingLLM()
    assistant = LegalAssistant(
        llm_client=client, legal_search=FakeLegalSearch(),
        cache=AnalysisCache(tmp_path / "quick-cache.db"), use_cache=True,
    )

    result = assistant.analyze("合同到期未付款怎么办？", mode="quick")

    assert client.calls == 0
    assert result["analysis_mode"] == "quick"
    assert set(LegalAssistant.REQUIRED_FIELDS) <= result.keys()
    assert result["legal_basis"] and result["similar_cases"]


ANALYSIS = {
    "case_facts": ["双方签订合同，被告逾期付款。"],
    "legal_relationships": ["合同法律关系"],
    "dispute_issues": ["付款义务是否到期"],
    "legal_basis": [{
        "legal_basis": "《中华人民共和国民法典》第五百七十七条", "law_name": "中华人民共和国民法典",
        "article": "第五百七十七条", "legal_text": "不履行合同义务的，应承担违约责任。",
        "source_file": "knowledge_base/laws/civil_code_full.json", "source": "国家法律法规数据库",
    }],
    "risk_analysis": ["举证风险"],
    "litigation_strategy": ["先催告"],
    "next_steps": ["整理证据"],
}


class CountingAnalysisGenerator:
    def __init__(self):
        self.calls = 0

    def generate(self, case, consultations):
        self.calls += 1
        return ANALYSIS, CaseLegalAnalysisReportGenerator._build_docx(case, ANALYSIS)


def test_repeated_case_analysis_uses_cache(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("货款纠纷", "甲 / 乙", "合同纠纷")
    manager.add_record(case.case_id, "legal_consultation", "咨询", {"question": "如何追款"})
    generator = CountingAnalysisGenerator()
    workflow = CaseWorkflow(manager, analysis_generator=generator, analysis_cache=AnalysisCache(manager.database_path))

    first, first_doc = workflow.generate_case_analysis(case.case_id)
    second, second_doc = workflow.generate_case_analysis(case.case_id)

    assert generator.calls == 1
    assert first == second == ANALYSIS
    assert first_doc.startswith(b"PK") and second_doc.startswith(b"PK")
    cache_flags = [event.details.get("cache_hit") for event in manager.list_events(case.case_id) if event.event_type == "legal_analysis"]
    assert set(cache_flags) == {False, True}


def test_complete_consultation_is_reused_without_analysis_llm_call(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("货款纠纷", "甲 / 乙", "合同纠纷")
    consultation = {
        "facts": ANALYSIS["case_facts"], "legal_relationships": ANALYSIS["legal_relationships"],
        "dispute_issues": ANALYSIS["dispute_issues"], "legal_basis": ANALYSIS["legal_basis"],
        "risk_warnings": ANALYSIS["risk_analysis"], "lawyer_advice": ANALYSIS["litigation_strategy"],
        "recommended_actions": ANALYSIS["next_steps"], "similar_cases": [{"case_name": "货款类案"}],
    }
    manager.add_record(case.case_id, "legal_consultation", "完整咨询", {"question": "如何追款", "analysis": consultation})
    generator = CountingAnalysisGenerator()

    analysis, document = CaseWorkflow(manager, analysis_generator=generator).generate_case_analysis(case.case_id)

    assert generator.calls == 0
    assert analysis["source"] == "legal_consultation_reuse"
    assert analysis["similar_cases"] == consultation["similar_cases"]
    assert document.startswith(b"PK")


def test_lawyer_final_opinion_is_saved_to_record_and_memory(tmp_path):
    database = tmp_path / "cases.db"
    manager = CaseManager(database)
    case = manager.create_case("货款纠纷", "甲 / 乙", "合同纠纷")

    LawyerMemory(manager).confirm_final_opinion(case.case_id, "证据齐备后提起买卖合同之诉。")
    reopened = CaseManager(database)
    memory = LawyerMemory(reopened).load(case.case_id, sync=True)

    assert memory.legal_analysis["lawyer_final_opinion"] == "证据齐备后提起买卖合同之诉。"
    assert any(record.record_type == "lawyer_confirmation" for record in reopened.list_records(case.case_id))
    assert any(event.event_type == "lawyer_confirmation" for event in reopened.list_events(case.case_id))
