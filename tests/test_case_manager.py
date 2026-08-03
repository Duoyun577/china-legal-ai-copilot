from pathlib import Path

import pytest

from case_manager import CaseManager


def test_case_manager_persists_case_records_and_files(tmp_path: Path) -> None:
    database_path = tmp_path / "cases.db"
    manager = CaseManager(database_path)

    case = manager.create_case("软件服务合同纠纷", "甲公司 / 乙公司", "合同纠纷")
    consultation = manager.add_record(
        case.case_id,
        "legal_consultation",
        "付款违约咨询",
        {"question_analysis": "存在逾期付款风险", "recommended_actions": ["发送催告函"]},
    )
    search = manager.add_record(
        case.case_id,
        "legal_search",
        "检索违约责任",
        [{"citation": "《中华人民共和国民法典》第五百七十七条"}],
    )
    contract_content = "合同正文".encode("utf-8")
    uploaded = manager.save_file(case.case_id, "uploaded_contract", "../contract.txt", contract_content, "text/plain")
    generated = manager.save_file(
        case.case_id,
        "generated_document",
        "民事起诉状.docx",
        b"PK-test-docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    reopened = CaseManager(database_path)
    saved_case = reopened.get_case(case.case_id)
    records = reopened.list_records(case.case_id)
    files = reopened.list_files(case.case_id)

    assert saved_case.name == "软件服务合同纠纷"
    assert saved_case.parties == "甲公司 / 乙公司"
    assert saved_case.case_type == "合同纠纷"
    assert {record.record_id for record in records} == {consultation.record_id, search.record_id}
    assert records[0].content
    assert {file.file_id for file in files} == {uploaded.file_id, generated.file_id}
    assert uploaded.filename == "contract.txt"
    assert reopened.get_file_content(uploaded.file_id) == contract_content
    assert "case_created" in {event.event_type for event in reopened.list_events(case.case_id)}
    assert any(event.title == "生成文件：民事起诉状.docx" for event in reopened.list_events(case.case_id))


def test_case_manager_rejects_incomplete_case(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path / "cases.db")

    with pytest.raises(ValueError, match="均不能为空"):
        manager.create_case("", "甲公司", "合同纠纷")


def test_case_manager_rejects_unknown_case_relations(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path / "cases.db")

    with pytest.raises(KeyError, match="案件不存在"):
        manager.add_record(999, "legal_search", "检索", {})

    with pytest.raises(KeyError, match="案件不存在"):
        manager.save_file(999, "uploaded_contract", "contract.txt", b"text", "text/plain")


def test_case_timeline_persists_business_events(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("买卖合同纠纷", "甲方 / 乙方", "合同纠纷")

    manager.add_event(case.case_id, "legal_consultation", "完成法律咨询", {"question": "如何追款"})
    manager.add_event(case.case_id, "legal_search", "检索违约责任", {"result_count": 2})
    manager.add_event(case.case_id, "contract_review", "完成合同审查", {"risk_count": 3})
    manager.add_event(case.case_id, "document_generation", "生成民事起诉状", {})

    events = list(reversed(manager.list_events(case.case_id)))

    assert [event.event_type for event in events] == [
        "case_created", "legal_consultation", "legal_search", "contract_review", "document_generation"
    ]
    assert events[1].details["question"] == "如何追款"
