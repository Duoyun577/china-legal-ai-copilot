"""咨询、诉状和合同修改的统一律师审核确认流程。"""

from __future__ import annotations

from dataclasses import dataclass

from case_manager.repository import CaseManager, CaseRecord


@dataclass(frozen=True)
class LawyerReview:
    artifact_type: str
    status: str
    opinion: str
    artifact_refs: list[str]
    record: CaseRecord


class LawyerReviewService:
    ARTIFACT_TYPES = {"consultation", "pleading", "contract_revision"}
    STATUSES = {"approved", "revision_required", "rejected"}

    def __init__(self, manager: CaseManager) -> None:
        self._manager = manager

    def confirm(
        self, case_id: int, artifact_type: str, opinion: str, *,
        status: str = "approved", artifact_refs: list[str] | None = None,
        related_analysis: dict | None = None,
    ) -> LawyerReview:
        if artifact_type not in self.ARTIFACT_TYPES:
            raise ValueError(f"不支持的律师审核类型：{artifact_type}")
        if status not in self.STATUSES:
            raise ValueError(f"不支持的律师审核状态：{status}")
        final_opinion = opinion.strip()
        if not final_opinion:
            raise ValueError("律师审核意见不能为空。")
        content = {
            "artifact_type": artifact_type,
            "status": status,
            "opinion": final_opinion,
            "final_opinion": final_opinion,
            "artifact_refs": artifact_refs or [],
            "related_analysis": related_analysis or {},
        }
        # 保留 lawyer_confirmation 类型，兼容 Final-011-E 的案件记忆与历史筛选。
        record = self._manager.add_record(case_id, "lawyer_confirmation", f"律师审核：{artifact_type}", content)
        self._manager.add_event(case_id, "lawyer_confirmation", f"律师确认 {artifact_type}", {
            "artifact_type": artifact_type, "status": status, "record_id": record.record_id,
        })
        return LawyerReview(artifact_type, status, final_opinion, content["artifact_refs"], record)

    def list_reviews(self, case_id: int, *, artifact_type: str | None = None) -> list[LawyerReview]:
        results = []
        for record in self._manager.list_records(case_id):
            if record.record_type != "lawyer_confirmation" or not isinstance(record.content, dict):
                continue
            current_type = str(record.content.get("artifact_type", "consultation"))
            if artifact_type and current_type != artifact_type:
                continue
            results.append(LawyerReview(
                current_type,
                str(record.content.get("status", "approved")),
                str(record.content.get("opinion", record.content.get("final_opinion", ""))),
                list(record.content.get("artifact_refs", [])),
                record,
            ))
        return results
