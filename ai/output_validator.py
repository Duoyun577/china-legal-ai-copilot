"""法律 AI 输出可信度验证层。

该模块只做结构、引用和规则编号核验，不判断模型结论是否替代律师意见。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ValidationResult:
    """验证结果；错误为空时 valid 为 True。"""

    valid: bool
    validation_errors: list[str] = field(default_factory=list)
    normalized_output: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为可直接返回给应用层的 JSON 兼容对象。"""
        return {
            "valid": self.valid,
            "validation_errors": self.validation_errors,
            "output": self.normalized_output,
        }


class LegalOutputValidator:
    """验证 AI 合同分析结果的必需字段、法律引用和风险编号。"""

    REQUIRED_FIELDS = ("contract_type", "clauses", "risks", "legal_basis", "recommendations")

    def __init__(self, laws_path: Path | None = None, rules_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self._laws_path = laws_path or root / "knowledge_base" / "laws"
        self._rules_path = rules_path or root / "rule_engine" / "contract_rules.json"

    def validate_json(self, output: str | dict[str, Any]) -> ValidationResult:
        """解析并验证 JSON 输出，错误统一放入 validation_errors。

        TODO: 增加 JSON Schema 校验、字段类型约束和版本兼容策略。
        TODO: 对风险证据做原文回查，避免模型生成合同中不存在的引文。
        TODO: 接入 LLM 评审器进行二次一致性检查，但不能替代规则校验。
        """
        errors: list[str] = []
        payload: Any = output
        if isinstance(output, str):
            try:
                payload = json.loads(output)
            except json.JSONDecodeError as exc:
                return ValidationResult(False, [f"输出不是有效 JSON：{exc.msg}"], None)
        if not isinstance(payload, dict):
            return ValidationResult(False, ["AI 输出必须是 JSON 对象。"], None)

        errors.extend(self._validate_structure(payload))
        if isinstance(payload.get("risks"), list):
            errors.extend(self._validate_risk_ids(payload["risks"]))
        if isinstance(payload.get("legal_basis"), list):
            errors.extend(self._validate_legal_basis(payload["legal_basis"]))
        return ValidationResult(not errors, errors, payload)

    def validate_mock_response(self, response: Any) -> ValidationResult:
        """验证 MockLLMClient 或其他客户端返回的 response.content。"""
        content = getattr(response, "content", response)
        if getattr(response, "is_mock", False) and isinstance(content, str) and content.startswith("[MOCK:json] "):
            content = content[len("[MOCK:json] "):]
        return self.validate_json(content)

    def _validate_structure(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for field_name in self.REQUIRED_FIELDS:
            if field_name not in payload:
                errors.append(f"缺少必需字段：{field_name}")
        expected_lists = ("clauses", "risks", "legal_basis", "recommendations")
        for field_name in expected_lists:
            if field_name in payload and not isinstance(payload[field_name], list):
                errors.append(f"字段必须为 JSON 数组：{field_name}")
        if "contract_type" in payload and not isinstance(payload["contract_type"], str):
            errors.append("字段必须为字符串：contract_type")
        return errors

    def _validate_risk_ids(self, risks: list[Any]) -> list[str]:
        known_ids = self._load_rule_ids()
        errors: list[str] = []
        for index, risk in enumerate(risks):
            if not isinstance(risk, dict):
                errors.append(f"risks[{index}] 必须是 JSON 对象。")
                continue
            rule_id = risk.get("rule_id")
            if not isinstance(rule_id, str):
                errors.append(f"risks[{index}] 缺少字符串 rule_id。")
            elif rule_id not in known_ids:
                errors.append(f"风险编号不存在：{rule_id}")
        return errors

    def _validate_legal_basis(self, legal_basis: list[Any]) -> list[str]:
        citations = self._load_law_citations()
        errors: list[str] = []
        for index, citation in enumerate(legal_basis):
            if not isinstance(citation, dict):
                errors.append(f"legal_basis[{index}] 必须是 JSON 对象。")
                continue
            article = citation.get("article")
            law_name = citation.get("law_name")
            if not isinstance(article, str) or not isinstance(law_name, str):
                errors.append(f"legal_basis[{index}] 必须包含字符串 law_name 和 article。")
                continue
            if (law_name, article) not in citations:
                errors.append(f"法律引用未在本地法律库找到：{law_name} {article}")
        return errors

    def _load_rule_ids(self) -> set[str]:
        with self._rules_path.open("r", encoding="utf-8") as file:
            return {rule["rule_id"] for rule in json.load(file).get("rules", [])}

    def _load_law_citations(self) -> set[tuple[str, str]]:
        citations: set[tuple[str, str]] = set()
        for path in self._laws_path.glob("*.json"):
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            records: Iterable[dict[str, Any]] = payload if isinstance(payload, list) else payload.get("records", [])
            for record in records:
                if isinstance(record, dict) and isinstance(record.get("law_name"), str) and isinstance(record.get("article"), str):
                    citations.add((record["law_name"], record["article"]))
        return citations
