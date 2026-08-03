"""从案件 SQLite 数据计算律师首页 Dashboard。"""

from __future__ import annotations

from dataclasses import dataclass

from case_manager.repository import CaseManager, CaseSummary, StoredFile


@dataclass(frozen=True)
class PendingItem:
    case_id: int
    case_name: str
    action: str


@dataclass(frozen=True)
class RecentFile:
    case_id: int
    case_name: str
    file: StoredFile


@dataclass(frozen=True)
class RiskReminder:
    case_id: int
    case_name: str
    level: str
    risk_count: int
    risk_score: int


@dataclass(frozen=True)
class LawyerDashboard:
    case_count: int
    recent_cases: list[CaseSummary]
    pending_items: list[PendingItem]
    recent_files: list[RecentFile]
    risk_reminders: list[RiskReminder]


def build_lawyer_dashboard(manager: CaseManager, *, limit: int = 5) -> LawyerDashboard:
    cases = manager.list_cases()
    pending: list[PendingItem] = []
    recent_files: list[RecentFile] = []
    reminders: list[RiskReminder] = []
    for case in cases:
        records = manager.list_records(case.case_id)
        record_types = {record.record_type for record in records}
        if "legal_consultation" not in record_types:
            pending.append(PendingItem(case.case_id, case.name, "待完成法律咨询"))
        elif "case_legal_analysis" not in record_types:
            pending.append(PendingItem(case.case_id, case.name, "待生成案件法律分析报告"))
        elif "delivery_package" not in record_types:
            pending.append(PendingItem(case.case_id, case.name, "待生成诉讼交付材料包"))
        for file in manager.list_files(case.case_id):
            if file.category == "generated_document":
                recent_files.append(RecentFile(case.case_id, case.name, file))
        for record in records:
            if record.record_type != "contract_review" or not isinstance(record.content, dict):
                continue
            level = str(record.content.get("overall_level", "LOW"))
            if level == "HIGH":
                reminders.append(
                    RiskReminder(
                        case.case_id, case.name, level,
                        int(record.content.get("risk_count", 0)), int(record.content.get("risk_score", 0)),
                    )
                )
                break
    recent_files.sort(key=lambda item: (item.file.created_at, item.file.file_id), reverse=True)
    reminders.sort(key=lambda item: (-item.risk_score, item.case_id))
    return LawyerDashboard(
        case_count=len(cases), recent_cases=cases[:limit], pending_items=pending[:limit],
        recent_files=recent_files[:limit], risk_reminders=reminders[:limit],
    )
