from io import BytesIO
import json
from pathlib import Path

from docx import Document

from ai.llm_client import LLMResponse
from case_manager import CaseManager
from case_manager.workflow import CaseWorkflow
from legal_assistant.case_analysis_report import CaseLegalAnalysisReportGenerator
from legal_assistant.legal_search_adapter import LegalCitation


ANALYSIS = {
    "case_facts": ["双方签订合同，被告逾期付款。"],
    "legal_relationships": ["双方形成合同法律关系。"],
    "dispute_issues": ["付款义务是否到期。"],
    "legal_basis": ["《中华人民共和国民法典》第五百七十七条。"],
    "risk_analysis": ["付款证据完整性需核实。"],
    "litigation_strategy": ["先发送书面催告并固定证据。"],
    "next_steps": ["核对合同、发票和付款记录。"],
}


class FakeLLMClient:
    def complete(self, messages, *, response_format="text") -> LLMResponse:
        return LLMResponse(content=json.dumps(ANALYSIS, ensure_ascii=False), model="test", is_mock=True)


class FakeLegalSearch:
    def search(self, question: str, *, top_k: int = 5) -> list[LegalCitation]:
        return [LegalCitation(
            law_name="中华人民共和国民法典",
            article="第五百七十七条",
            legal_text="当事人一方不履行合同义务的，应当承担违约责任。",
            source="国家法律法规数据库",
            citation="《中华人民共和国民法典》第五百七十七条",
            score=9.0,
            source_file="knowledge_base/laws/civil_code_full.json",
        )]


class FakeComplaintGenerator:
    def __init__(self) -> None:
        self.context = ""

    def generate(self, case_facts: str) -> bytes:
        self.context = case_facts
        return b"PK-complaint"


def test_case_analysis_report_contains_all_required_sections(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("服务合同纠纷", "甲公司 / 乙公司", "合同纠纷")
    manager.add_record(case.case_id, "legal_consultation", "付款咨询", {"question": "如何追款"})

    analysis, content = CaseLegalAnalysisReportGenerator(FakeLLMClient(), legal_search=FakeLegalSearch()).generate(
        case, [record for record in manager.list_records(case.case_id) if record.record_type == "legal_consultation"]
    )
    document = Document(BytesIO(content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert analysis["case_facts"] == ANALYSIS["case_facts"]
    assert analysis["legal_basis"][0]["article"] == "第五百七十七条"
    assert analysis["legal_basis"][0]["source_file"] == "knowledge_base/laws/civil_code_full.json"
    for heading in ("案件事实整理", "法律关系分析", "争议焦点", "法律依据", "风险分析", "诉讼策略", "下一步建议"):
        assert heading in text
    for label in ("法律名称：", "条文编号：", "条文内容：", "来源文件："):
        assert label in text


def test_case_workflow_saves_analysis_and_generates_complaint(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("服务合同纠纷", "甲公司 / 乙公司", "合同纠纷")
    manager.add_record(case.case_id, "legal_consultation", "付款咨询", {"question": "如何追款", "analysis": {}})
    complaint_generator = FakeComplaintGenerator()
    workflow = CaseWorkflow(
        manager,
        analysis_generator=CaseLegalAnalysisReportGenerator(FakeLLMClient(), legal_search=FakeLegalSearch()),
        complaint_generator=complaint_generator,
    )

    analysis, report = workflow.generate_case_analysis(case.case_id)
    complaint = workflow.generate_complaint_from_case(case.case_id)

    assert analysis["case_facts"] == ANALYSIS["case_facts"]
    assert report.startswith(b"PK")
    assert complaint == b"PK-complaint"
    context = json.loads(complaint_generator.context)
    assert context["案件信息"]["案件名称"] == case.name
    assert context["法律咨询记录"]
    assert context["案件法律分析"]["legal_basis"][0]["article"] == "第五百七十七条"
    assert {record.record_type for record in manager.list_records(case.case_id)} >= {
        "legal_consultation", "case_legal_analysis", "document_generation"
    }
    assert {file.filename for file in manager.list_files(case.case_id)} == {
        "案件法律分析报告.docx", "基于案件分析_民事起诉状.docx"
    }
    assert {event.event_type for event in manager.list_events(case.case_id)} >= {
        "case_created", "legal_analysis", "document_generation"
    }
