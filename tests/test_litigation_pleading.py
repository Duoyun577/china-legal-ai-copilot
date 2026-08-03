from io import BytesIO
import json

from docx import Document

from ai.llm_client import LLMResponse
from case_manager import CaseManager
from case_manager.workflow import CaseWorkflow
from lawsuit_generator.pleading_service import LitigationPleadingService


LEGAL_BASIS = {
    "legal_basis": "《中华人民共和国民法典》第五百七十七条",
    "law_name": "中华人民共和国民法典",
    "article": "第五百七十七条",
    "legal_text": "当事人一方不履行合同义务的，应当承担违约责任。",
    "source_file": "knowledge_base/laws/civil_code_full.json",
    "source": "国家法律法规数据库",
}
SIMILAR_CASE = {
    "case_name": "买卖合同逾期付款类案",
    "court": "某区人民法院（脱敏）",
    "case_facts": "买方签收后未付款。",
    "judgment_result": "判令支付货款。",
    "court_opinion": "签收和对账记录可形成证据链。",
    "lawyer_insights": "固定签收、对账和催款记录。",
}
PLAN = {
    "cause_of_action": "买卖合同纠纷",
    "dispute_issues": ["付款义务是否届期"],
    "claims": ["判令被告支付货款人民币100000元及逾期付款损失。", "本案诉讼费用由被告承担。"],
    "facts_and_reasons": ["原被告签订买卖合同，原告交付货物后被告未按期付款。"],
    "parties": [{"原告": "甲公司，住所地及统一社会信用代码【待填写】"}, {"被告": "乙公司，住所地及统一社会信用代码【待填写】"}],
    "court": "【待确认有管辖权的人民法院】",
    "evidence_system": [{"name": "买卖合同及签收单", "source": "原告持有", "purpose": "证明合同及交付", "status": "待核验原件"}],
    "risks": ["被告财产状况及执行风险待核实"],
    "litigation_strategy": ["起诉前核查财产线索并评估保全"],
    "procedural_uncertainties": ["管辖法院待核实"],
}


class FakeLLM:
    def __init__(self):
        self.prompt = ""

    def complete(self, messages, *, response_format="text"):
        self.prompt = messages[0].content
        return LLMResponse(json.dumps(PLAN, ensure_ascii=False), "test", True)


def text_of(content):
    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def build_case(manager):
    case = manager.create_case("货款纠纷", "甲公司 / 乙公司", "合同纠纷")
    consultation = {
        "facts": ["原告交货后被告未付款。"],
        "legal_relationships": ["买卖合同关系"],
        "dispute_issues": ["付款义务是否届期"],
        "legal_basis": [LEGAL_BASIS],
        "similar_cases": [SIMILAR_CASE],
        "evidence_recommendations": ["核验合同和签收单"],
    }
    manager.add_record(case.case_id, "legal_consultation", "货款咨询", {"question": "如何起诉追款", "analysis": consultation})
    manager.add_record(case.case_id, "case_legal_analysis", "案件法律分析报告", {
        "case_facts": consultation["facts"], "legal_relationships": consultation["legal_relationships"],
        "dispute_issues": consultation["dispute_issues"], "legal_basis": [LEGAL_BASIS],
        "risk_analysis": PLAN["risks"], "litigation_strategy": PLAN["litigation_strategy"],
    })
    return case


def test_pleading_service_outputs_distinct_lawyer_and_court_versions():
    client = FakeLLM()
    service = LitigationPleadingService(client)
    documents = service.generate({
        "案件长期记忆": {"case_facts": ["已交货未付款"]},
        "案件法律分析": {"risk_analysis": PLAN["risks"]},
        "verified_legal_basis": [LEGAL_BASIS],
        "verified_similar_cases": [SIMILAR_CASE],
    })

    lawyer_text = text_of(documents.lawyer_version)
    court_text = text_of(documents.court_version)
    assert documents.lawyer_version.startswith(b"PK") and documents.court_version.startswith(b"PK")
    for heading in ("案件记忆", "案件分析", "案由判断", "争议焦点", "法律依据", "类案参考", "证据体系", "诉讼风险", "诉讼策略"):
        assert heading in lawyer_text
    assert court_text.startswith("民事起诉状")
    assert "诉讼请求" in court_text and "事实与理由" in court_text and "此致" in court_text and "具状人" in court_text
    assert "《中华人民共和国民法典》第五百七十七条" in court_text
    assert all(marker not in court_text for marker in LitigationPleadingService.FORBIDDEN_COURT_MARKERS)
    assert "类案参考" not in court_text and "诉讼风险" not in court_text
    assert "verified_legal_basis" in client.prompt and "verified_similar_cases" in client.prompt


def test_case_workflow_reads_memory_and_saves_two_versions(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = build_case(manager)
    client = FakeLLM()
    workflow = CaseWorkflow(manager, pleading_service=LitigationPleadingService(client))

    result = workflow.generate_pleadings_from_case(case.case_id)

    assert set(result) == {"lawyer_version", "court_version"}
    assert {item.filename for item in manager.list_files(case.case_id)} == {
        "民事起诉状_律师工作版.docx", "民事起诉状_法院提交版.docx",
    }
    assert "案件长期记忆" in client.prompt
    assert "法律咨询结果" in client.prompt
    assert "第五百七十七条" in client.prompt
    assert "买卖合同逾期付款类案" in client.prompt


def test_legacy_single_complaint_api_returns_court_version(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = build_case(manager)
    workflow = CaseWorkflow(manager, pleading_service=LitigationPleadingService(FakeLLM()))

    content = workflow.generate_complaint_from_case(case.case_id)

    assert text_of(content).startswith("民事起诉状")
    assert "AI" not in text_of(content)
