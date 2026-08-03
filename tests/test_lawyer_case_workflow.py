from case_manager import CaseInitializer, CaseManager, EvidenceManager
from legal_assistant.hearing_assistant import HearingAssistant
from lawyer_memory import LawyerMemory


ANALYSIS = {
    "facts": ["甲公司向乙公司交付货物，乙公司未支付到期货款。"],
    "case_type": "买卖合同纠纷",
    "legal_relationships": ["买卖合同法律关系"],
    "dispute_issues": ["货款支付义务是否到期", "逾期付款损失如何计算"],
    "legal_basis": [],
    "similar_cases": [],
    "risk_warnings": ["签收证据待核实"],
    "lawyer_advice": ["整理合同和签收材料"],
}


def test_first_consultation_initializes_case_fields(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")

    case = CaseInitializer(manager).initialize("对方收货后不支付货款怎么办？", ANALYSIS)
    record = next(item for item in manager.list_records(case.case_id) if item.record_type == "case_initialization")

    assert case.name.startswith("买卖合同纠纷｜")
    assert case.case_type == "买卖合同纠纷"
    assert case.parties == "【待补充当事人】"
    assert record.content["case_facts"] == ANALYSIS["facts"]
    assert record.content["dispute_issues"] == ANALYSIS["dispute_issues"]
    memory = LawyerMemory(manager).load(case.case_id, sync=True)
    assert memory.case_facts == ANALYSIS["facts"]
    assert memory.dispute_issues == ANALYSIS["dispute_issues"]
    assert any(event.event_type == "case_initialization" for event in manager.list_events(case.case_id))


def test_evidence_manager_classifies_existing_and_missing_evidence(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("货款纠纷", "甲公司 / 乙公司", "合同纠纷")
    evidence = EvidenceManager(manager)

    evidence.add(case.case_id, "买卖合同", "书证", "existing", "证明合同关系成立", "仅有扫描件，需核验原件")
    evidence.add(case.case_id, "货物签收单", "书证", "missing", "证明货物已经交付", "缺失将影响履行事实认定")
    summary = evidence.summarize(case.case_id)
    memory = LawyerMemory(manager).load(case.case_id, sync=True)

    assert [item.name for item in summary.existing] == ["买卖合同"]
    assert [item.name for item in summary.missing] == ["货物签收单"]
    assert set(summary.by_category) == {"书证"}
    assert summary.existing[0].proof_purpose == "证明合同关系成立"
    assert "原件" in summary.existing[0].risk
    assert any(item["name"] == "货物签收单" and item["status"] == "missing" for item in memory.evidence_status)


def test_evidence_manager_normalizes_fields_and_applies_default_risk(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("货款纠纷", "甲公司 / 乙公司", "合同纠纷")

    item = EvidenceManager(manager).add(
        case.case_id, "  微信聊天记录  ", " 电子数据 ", " existing ", " 证明付款承诺 ", " ",
    )

    assert item.name == "微信聊天记录"
    assert item.category == "电子数据"
    assert item.status == "existing"
    assert item.proof_purpose == "证明付款承诺"
    assert "真实性、合法性和关联性" in item.risk


def test_hearing_assistant_uses_disputes_and_evidence_risks(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = CaseInitializer(manager).initialize("对方收货后不支付货款怎么办？", ANALYSIS)
    manager.add_record(case.case_id, "legal_consultation", "首次咨询", {"question": "如何追款", "analysis": ANALYSIS})
    evidence = EvidenceManager(manager)
    evidence.add(case.case_id, "买卖合同", "书证", "existing", "证明合同关系成立", "需提交原件")
    evidence.add(case.case_id, "签收单", "书证", "missing", "证明交货", "缺失可能导致交付事实无法证明")

    plan = HearingAssistant(manager).generate(case.case_id)

    assert any("货款支付义务是否到期" in item for item in plan.hearing_outline)
    assert any("货款支付义务是否到期" in item for item in plan.examination_questions)
    assert plan.possible_defenses
    assert plan.response_strategies
    assert any("签收单" in item and "缺失" in item for item in plan.evidence_alerts)
    assert any(record.record_type == "hearing_plan" for record in manager.list_records(case.case_id))
    assert any(event.event_type == "hearing_preparation" for event in manager.list_events(case.case_id))


def test_hearing_assistant_uses_issues_from_initialization_without_consultation_record(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = CaseInitializer(manager).initialize("对方收货后不支付货款怎么办？", ANALYSIS)

    plan = HearingAssistant(manager).generate(case.case_id)

    assert any("货款支付义务是否到期" in item for item in plan.hearing_outline)
    assert any("逾期付款损失如何计算" in item for item in plan.examination_questions)
