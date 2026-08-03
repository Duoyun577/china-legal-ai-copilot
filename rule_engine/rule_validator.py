"""合同风险规则质量校验工具。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuleQualityFinding:
    """单条规则的质量发现项。"""

    rule_id: str
    level: str
    issue: str
    evidence: list[str]
    recommendation: str


class ContractRuleValidator:
    """识别高泛化触发词、字段缺失和风险等级配置问题。"""

    _generic_keywords = {
        "甲方", "乙方", "合同", "公司", "服务", "付款", "交付", "验收", "违约", "解除", "仲裁", "诉讼",
    }
    _required_fields = {
        "rule_id", "category", "name", "trigger_keywords", "risk_level", "risk_score",
        "description", "legal_issue", "legal_basis", "suggestion", "applicable_contracts", "review_focus", "version",
    }
    _valid_levels = {"HIGH", "MIDDLE", "LOW"}

    def validate_file(self, rules_path: Path) -> list[RuleQualityFinding]:
        """读取并检查现有 contract_rules.json。

        TODO: 使用 LLM 根据真实合同语料估计规则精确率、召回率和误报率。
        TODO: 支持从 evaluation 数据集中生成规则回归测试和覆盖率报告。
        TODO: 对触发词增加上下文条件、否定条件与条款类型约束。
        """
        with rules_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return [finding for rule in payload["rules"] for finding in self.validate_rule(rule)]

    def validate_rule(self, rule: dict[str, Any]) -> list[RuleQualityFinding]:
        """检查单条规则的基础质量与过度触发风险。"""
        findings: list[RuleQualityFinding] = []
        rule_id = rule.get("rule_id", "UNKNOWN")
        missing = sorted(self._required_fields - set(rule))
        if missing:
            findings.append(RuleQualityFinding(rule_id, "ERROR", "必填字段缺失", missing, "补齐规则标准字段。"))
        if rule.get("risk_level") not in self._valid_levels:
            findings.append(RuleQualityFinding(rule_id, "ERROR", "风险等级不规范", [str(rule.get("risk_level"))], "仅使用 HIGH、MIDDLE 或 LOW。"))
        keywords = rule.get("trigger_keywords", [])
        generic = [keyword for keyword in keywords if keyword in self._generic_keywords]
        if generic:
            findings.append(
                RuleQualityFinding(
                    rule_id,
                    "WARNING",
                    "存在过度触发风险",
                    generic,
                    "通用词不能单独认定风险；应增加上下文、缺失条件、条款位置或多个关键词组合。",
                )
            )
        if len(keywords) < 2:
            findings.append(RuleQualityFinding(rule_id, "WARNING", "触发词过少", keywords, "补充同义表达、反向条件和条款级约束。"))
        return findings
