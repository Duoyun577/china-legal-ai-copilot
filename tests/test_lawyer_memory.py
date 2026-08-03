import json

from case_manager import CaseManager, CaseMemoryStore
from case_manager.workflow import CaseWorkflow
from lawyer_memory import LawyerMemory


class FakeComplaintGenerator:
    def __init__(self):
        self.context = ""

    def generate(self, context):
        self.context = context
        return b"PK-memory"


def consultation_analysis():
    return {
        "facts": ["双方签订合同，买方尚欠货款。"],
        "legal_relationships": ["买卖合同法律关系"],
        "dispute_issues": ["货款是否到期"],
        "question_analysis": "买方可能构成违约。",
        "similar_cases": [{"case_name": "逾期货款类案", "court": "某法院"}],
        "evidence_recommendations": ["核对合同和签收单"],
        "uncertain_facts": ["付款期限"],
    }


def test_lawyer_memory_persists_all_consultation_dimensions(tmp_path):
    database = tmp_path / "cases.db"
    manager = CaseManager(database)
    case = manager.create_case("货款纠纷", "甲公司 / 乙公司", "合同纠纷")

    memory = LawyerMemory(manager).remember_consultation(case.case_id, "如何追回货款？", consultation_analysis())
    reopened = LawyerMemory(CaseManager(database)).load(case.case_id)

    assert memory.case_facts == ["双方签订合同，买方尚欠货款。"]
    assert reopened.legal_relationships == ["买卖合同法律关系"]
    assert reopened.dispute_issues == ["货款是否到期"]
    assert reopened.legal_analysis["question_analysis"] == "买方可能构成违约。"
    assert reopened.similar_cases[0]["case_name"] == "逾期货款类案"
    assert reopened.evidence_status
    assert reopened.consultation_history[0]["question"] == "如何追回货款？"


def test_opening_legacy_case_rebuilds_memory_from_history(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("历史案件", "甲 / 乙", "合同纠纷")
    manager.add_record(case.case_id, "legal_consultation", "历史咨询", {"question": "是否违约？", "analysis": consultation_analysis()})

    memory = LawyerMemory(manager).load(case.case_id, sync=True)

    assert memory.case_facts
    assert memory.consultation_history[0]["question"] == "是否违约？"
    assert CaseMemoryStore(manager.database_path).load(case.case_id).updated_at


def test_complaint_workflow_includes_long_term_case_memory(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("货款纠纷", "甲 / 乙", "合同纠纷")
    analysis = consultation_analysis()
    manager.add_record(case.case_id, "legal_consultation", "咨询", {"question": "如何追款", "analysis": analysis})
    manager.add_record(case.case_id, "case_legal_analysis", "案件法律分析报告", analysis)
    complaint = FakeComplaintGenerator()

    content = CaseWorkflow(manager, complaint_generator=complaint).generate_complaint_from_case(case.case_id)
    context = json.loads(complaint.context)

    assert content == b"PK-memory"
    assert context["案件长期记忆"]["case_facts"] == analysis["facts"]
    assert context["案件长期记忆"]["consultation_history"]
