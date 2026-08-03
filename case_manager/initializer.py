"""根据首次法律咨询自动初始化案件。"""

from __future__ import annotations

from case_manager.repository import CaseManager, CaseSummary


class CaseInitializer:
    def __init__(self, manager: CaseManager) -> None:
        self._manager = manager

    def initialize(self, question: str, analysis: dict) -> CaseSummary:
        facts = self._list(analysis.get("facts"))
        issues = self._list(analysis.get("dispute_issues"))
        case_type = str(analysis.get("case_type") or "待判断法律事项").strip()
        fact_label = (str(facts[0])[:24] if facts else question.strip()[:24]) or "首次法律咨询"
        name = f"{case_type}｜{fact_label}"
        case = self._manager.create_case(name, "【待补充当事人】", case_type)
        self._manager.add_record(case.case_id, "case_initialization", "首次咨询自动初始化", {
            "question": question.strip(), "case_name": name, "case_type": case_type,
            "case_facts": facts, "dispute_issues": issues,
        })
        self._manager.add_event(case.case_id, "case_initialization", "根据首次咨询初始化案件", {
            "fact_count": len(facts), "issue_count": len(issues),
        })
        return case

    @staticmethod
    def _list(value) -> list:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]
