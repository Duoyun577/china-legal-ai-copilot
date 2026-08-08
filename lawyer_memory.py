"""Persistent case-memory service used by the lawyer workflows."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from case_manager.memory import CaseMemory, CaseMemoryStore
from case_manager.repository import CaseManager


class LawyerMemory:
    """Keep the derived case memory in sync with existing case records."""

    def __init__(self, manager: CaseManager) -> None:
        self._manager = manager
        self._store = CaseMemoryStore(manager.database_path)

    def load(self, case_id: int, *, sync: bool = False) -> CaseMemory:
        self._manager.get_case(case_id)
        return self.sync(case_id) if sync else self._store.load(case_id)

    def sync(self, case_id: int) -> CaseMemory:
        """Rebuild memory from durable records, including legacy cases."""
        self._manager.get_case(case_id)
        memory = CaseMemory(case_id=case_id)

        for record in reversed(self._manager.list_records(case_id)):
            content = record.content if isinstance(record.content, dict) else {}

            if record.record_type == "case_initialization":
                memory = replace(
                    memory,
                    case_facts=self._merge(memory.case_facts, content.get("case_facts")),
                    dispute_issues=self._merge(memory.dispute_issues, content.get("dispute_issues")),
                )
            elif record.record_type in {"legal_consultation", "consultation_memory"}:
                analysis = content.get("analysis") if isinstance(content.get("analysis"), dict) else {}
                question = str(content.get("question", "")).strip()
                history_item = {"question": question, "analysis": analysis}
                history = list(memory.consultation_history)
                if question and history_item not in history:
                    history.append(history_item)
                memory = self._apply_consultation(memory, analysis, history)
            elif record.record_type == "case_legal_analysis":
                memory = self._apply_analysis(memory, content)
            elif record.record_type == "evidence_item":
                memory = replace(memory, evidence_status=self._merge(memory.evidence_status, [content]))
            elif record.record_type == "lawyer_confirmation":
                opinion = str(content.get("opinion", "")).strip()
                if opinion:
                    legal_analysis = dict(memory.legal_analysis) if isinstance(memory.legal_analysis, dict) else {}
                    legal_analysis["lawyer_final_opinion"] = opinion
                    legal_analysis["lawyer_review_status"] = content.get("status", "approved")
                    memory = replace(memory, legal_analysis=legal_analysis)

        return self._store.save(memory)

    def remember_consultation(self, case_id: int, question: str, analysis: dict) -> CaseMemory:
        self._manager.get_case(case_id)
        current = self._store.load(case_id)
        history_item = {"question": question.strip(), "analysis": analysis}
        history = list(current.consultation_history)
        if history_item not in history:
            history.append(history_item)
        return self._store.save(self._apply_consultation(current, analysis, history))

    def remember_analysis(self, case_id: int, analysis: dict) -> CaseMemory:
        self._manager.get_case(case_id)
        return self._store.save(self._apply_analysis(self._store.load(case_id), analysis))

    def confirm_final_opinion(
        self,
        case_id: int,
        opinion: str,
        *,
        status: str = "approved",
        related_analysis: dict | None = None,
    ) -> CaseMemory:
        self._manager.get_case(case_id)
        opinion = opinion.strip()
        if not opinion:
            raise ValueError("律师审核意见不能为空。")

        self._manager.add_record(
            case_id,
            "lawyer_confirmation",
            "律师最终审核确认",
            {
                "status": status,
                "opinion": opinion,
                "related_analysis": related_analysis or {},
            },
        )
        self._manager.add_event(
            case_id,
            "lawyer_confirmation",
            "律师完成审核确认",
            {"status": status},
        )
        return self.sync(case_id)

    @classmethod
    def _apply_consultation(
        cls,
        memory: CaseMemory,
        analysis: dict,
        history: list[Any],
    ) -> CaseMemory:
        evidence = analysis.get("evidence_status", analysis.get("evidence_recommendations"))
        return replace(
            memory,
            case_facts=cls._merge(memory.case_facts, analysis.get("facts", analysis.get("case_facts"))),
            legal_relationships=cls._merge(memory.legal_relationships, analysis.get("legal_relationships")),
            dispute_issues=cls._merge(memory.dispute_issues, analysis.get("dispute_issues")),
            legal_analysis={**(memory.legal_analysis if isinstance(memory.legal_analysis, dict) else {}), **analysis},
            similar_cases=cls._merge(memory.similar_cases, analysis.get("similar_cases")),
            evidence_status=cls._merge(memory.evidence_status, evidence),
            consultation_history=history,
        )

    @classmethod
    def _apply_analysis(cls, memory: CaseMemory, analysis: dict) -> CaseMemory:
        return replace(
            memory,
            case_facts=cls._merge(memory.case_facts, analysis.get("case_facts", analysis.get("facts"))),
            legal_relationships=cls._merge(memory.legal_relationships, analysis.get("legal_relationships")),
            dispute_issues=cls._merge(memory.dispute_issues, analysis.get("dispute_issues")),
            legal_analysis={**(memory.legal_analysis if isinstance(memory.legal_analysis, dict) else {}), **analysis},
            similar_cases=cls._merge(memory.similar_cases, analysis.get("similar_cases")),
        )

    @staticmethod
    def _merge(existing: list[Any], incoming: Any) -> list[Any]:
        values = incoming if isinstance(incoming, list) else ([] if incoming is None else [incoming])
        result = list(existing)
        for value in values:
            if value not in result:
                result.append(value)
        return result
