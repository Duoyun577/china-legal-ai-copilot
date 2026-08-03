"""离线合同审查流程编排服务。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rule_service import RuleMatch, RuleService


@dataclass(frozen=True)
class LegalBasis:
    """与风险规则关联的本地法律依据。"""

    law_name: str
    article: str
    legal_text: str
    source: str


@dataclass(frozen=True)
class ContractReviewResult:
    """离线审查流程的结构化结果。"""

    contract_path: Path
    contract_type: str
    risks: list[RuleMatch]
    legal_basis_by_rule: dict[str, list[LegalBasis]]


class ContractReviewService:
    """读取合同、匹配规则、关联本地法条并返回审查结果。"""

    def __init__(self, rule_service: RuleService | None = None, laws_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self._rule_service = rule_service or RuleService()
        self._laws_path = laws_path or project_root / "knowledge_base" / "laws" / "civil_code_contract.json"

    def review(self, contract_path: Path) -> ContractReviewResult:
        """执行离线审查流程：读取合同 → 规则匹配 → 法律依据关联。

        TODO: 接入 document_loader.py，支持 DOCX、PDF 和 OCR 文档。
        TODO: 接入 Contract Review Agent 的条款提取与合同分类能力。
        TODO: 接入 RAG 的 LegalSearchService 进行语义检索与重排序。
        """
        text = contract_path.read_text(encoding="utf-8")
        risks = self._rule_service.match(text)
        return ContractReviewResult(
            contract_path=contract_path,
            contract_type=self._classify_contract(text),
            risks=risks,
            legal_basis_by_rule=self._find_legal_basis(risks),
        )

    def _find_legal_basis(self, risks: list[RuleMatch]) -> dict[str, list[LegalBasis]]:
        """依据本地 law JSON 的 risk_rules 字段关联法律依据。"""
        with self._laws_path.open("r", encoding="utf-8") as file:
            laws = json.load(file)
        result: dict[str, list[LegalBasis]] = {}
        for risk in risks:
            result[risk.rule_id] = [
                LegalBasis(
                    law_name=law["law_name"],
                    article=law["article"],
                    legal_text=law["legal_text"],
                    source=law["source"],
                )
                for law in laws
                if risk.rule_id in law["risk_rules"]
            ]
        return result

    @staticmethod
    def _classify_contract(text: str) -> str:
        """以确定性关键词给出临时分类。"""
        if "软件" in text and ("开发" in text or "服务" in text):
            return "软件开发服务合同"
        return "未分类商业合同"
