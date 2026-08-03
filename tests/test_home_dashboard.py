from pathlib import Path

from case_manager import CaseManager
from case_manager.dashboard import build_lawyer_dashboard


def test_home_dashboard_summarizes_cases_pending_files_and_risks(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path / "cases.db")
    new_case = manager.create_case("待咨询案件", "甲 / 乙", "合同纠纷")
    analysis_case = manager.create_case("待分析案件", "丙 / 丁", "服务纠纷")
    delivery_case = manager.create_case("待交付案件", "戊 / 己", "买卖纠纷")
    complete_case = manager.create_case("高风险完成案件", "庚 / 辛", "合同纠纷")

    manager.add_record(analysis_case.case_id, "legal_consultation", "咨询", {})
    manager.add_record(delivery_case.case_id, "legal_consultation", "咨询", {})
    manager.add_record(delivery_case.case_id, "case_legal_analysis", "分析", {})
    manager.add_record(complete_case.case_id, "legal_consultation", "咨询", {})
    manager.add_record(complete_case.case_id, "case_legal_analysis", "分析", {})
    manager.add_record(complete_case.case_id, "delivery_package", "交付", {"files": []})
    manager.add_record(
        complete_case.case_id,
        "contract_review",
        "合同审查",
        {"overall_level": "HIGH", "risk_count": 8, "risk_score": 80},
    )
    generated = manager.save_file(
        complete_case.case_id, "generated_document", "民事起诉状.docx", b"PK-docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    dashboard = build_lawyer_dashboard(manager)

    assert dashboard.case_count == 4
    assert {item.action for item in dashboard.pending_items} == {
        "待完成法律咨询", "待生成案件法律分析报告", "待生成诉讼交付材料包"
    }
    assert dashboard.recent_files[0].file.file_id == generated.file_id
    assert dashboard.risk_reminders[0].case_id == complete_case.case_id
    assert dashboard.risk_reminders[0].risk_score == 80
    assert new_case.case_id in {case.case_id for case in dashboard.recent_cases}


def test_home_dashboard_respects_display_limit(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path / "cases.db")
    for index in range(7):
        manager.create_case(f"案件{index}", "甲 / 乙", "合同纠纷")

    dashboard = build_lawyer_dashboard(manager, limit=3)

    assert len(dashboard.recent_cases) == 3
    assert len(dashboard.pending_items) == 3
