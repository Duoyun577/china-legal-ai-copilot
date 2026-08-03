"""案件证据分类、状态、证明目的和风险管理。"""

from __future__ import annotations

from dataclasses import dataclass

from case_manager.repository import CaseManager


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: int
    case_id: int
    name: str
    category: str
    status: str
    proof_purpose: str
    risk: str
    created_at: str


@dataclass(frozen=True)
class EvidenceSummary:
    existing: list[EvidenceItem]
    missing: list[EvidenceItem]
    by_category: dict[str, list[EvidenceItem]]


class EvidenceManager:
    CATEGORIES = {"书证", "电子数据", "物证", "证人证言", "视听资料", "鉴定意见", "当事人陈述", "其他"}
    STATUSES = {"existing", "missing"}

    def __init__(self, manager: CaseManager) -> None:
        self._manager = manager

    def add(self, case_id: int, name: str, category: str, status: str, proof_purpose: str, risk: str = "") -> EvidenceItem:
        name, category, status, proof_purpose, risk = (
            name.strip(), category.strip(), status.strip(), proof_purpose.strip(), risk.strip(),
        )
        values = (name, category, status, proof_purpose)
        if not all(values):
            raise ValueError("证据名称、分类、状态和证明目的均不能为空。")
        if category not in self.CATEGORIES:
            raise ValueError(f"不支持的证据分类：{category}")
        if status not in self.STATUSES:
            raise ValueError(f"不支持的证据状态：{status}")
        record = self._manager.add_record(case_id, "evidence_item", f"证据：{name}", {
            "name": name, "category": category, "status": status,
            "proof_purpose": proof_purpose, "risk": risk or "暂无特别风险，提交前仍需核验真实性、合法性和关联性。",
        })
        self._manager.add_event(case_id, "evidence_management", f"登记证据：{name}", {"status": status, "category": category})
        return self._from_record(record)

    def list(self, case_id: int) -> list[EvidenceItem]:
        return [self._from_record(record) for record in self._manager.list_records(case_id) if record.record_type == "evidence_item"]

    def summarize(self, case_id: int) -> EvidenceSummary:
        items = self.list(case_id)
        categories: dict[str, list[EvidenceItem]] = {}
        for item in items:
            categories.setdefault(item.category, []).append(item)
        return EvidenceSummary(
            existing=[item for item in items if item.status == "existing"],
            missing=[item for item in items if item.status == "missing"],
            by_category=categories,
        )

    @staticmethod
    def _from_record(record) -> EvidenceItem:
        content = record.content
        return EvidenceItem(
            record.record_id, record.case_id, str(content["name"]), str(content["category"]),
            str(content["status"]), str(content["proof_purpose"]), str(content.get("risk", "")), record.created_at,
        )
