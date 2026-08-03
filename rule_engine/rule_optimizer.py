"""将关键词风险规则评估为可逐步升级的上下文规则模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OptimizationFinding:
    """单条风险规则的优化建议。"""

    rule_id: str
    category: str
    finding_type: str
    severity: str
    evidence: list[str]
    recommendation: str


@dataclass(frozen=True)
class OptimizationReport:
    """规则库优化分析的结构化报告。"""

    total_rules: int
    context_covered_rules: int
    findings: list[OptimizationFinding] = field(default_factory=list)

    def to_markdown(self) -> str:
        """输出供律师和规则维护人员阅读的 Markdown 报告。"""
        lines = [
            "# 合同审查规则库优化报告",
            "",
            f"- 规则总数：{self.total_rules}",
            f"- 上下文规则覆盖数：{self.context_covered_rules}",
            f"- 优化发现数：{len(self.findings)}",
            "",
            "| 规则 | 类型 | 严重度 | 证据 | 优化建议 |",
            "| --- | --- | --- | --- | --- |",
        ]
        lines.extend(
            f"| {item.rule_id} | {item.finding_type} | {item.severity} | {'；'.join(item.evidence)} | {item.recommendation} |"
            for item in self.findings
        )
        return "\n".join(lines)


class RuleOptimizer:
    """评估既有关键词规则并检查对应的上下文配置。"""

    _generic_keywords = {"甲方", "乙方", "合同", "公司", "服务", "付款", "交付", "验收", "违约", "解除", "仲裁", "诉讼"}
    _level_score_ranges = {"HIGH": (70, 100), "MIDDLE": (40, 69), "LOW": (0, 39)}

    def __init__(self, rules_path: Path | None = None, context_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parent
        self._rules_path = rules_path or root / "contract_rules.json"
        self._context_path = context_path or root / "rule_context.json"

    def analyze(self) -> OptimizationReport:
        """分析过度触发、上下文缺失及风险等级合理性。

        TODO: 接入 LLM，对真实合同条款判断触发词的语义、否定和例外。
        TODO: 读取评测集的误报/漏报结果，以数据校准上下文和评分阈值。
        TODO: 自动生成经人工批准后才可写回规则库的优化补丁。
        """
        rules = self._load_rules()
        contexts = {item["rule_id"]: item for item in self._load_contexts()}
        findings: list[OptimizationFinding] = []
        for rule in rules:
            findings.extend(self._analyze_rule(rule, contexts.get(rule["rule_id"])))
        return OptimizationReport(len(rules), len(contexts), findings)

    def _analyze_rule(self, rule: dict[str, Any], context: dict[str, Any] | None) -> list[OptimizationFinding]:
        findings: list[OptimizationFinding] = []
        rule_id = rule["rule_id"]
        generic = [word for word in rule["trigger_keywords"] if word in self._generic_keywords]
        if generic:
            findings.append(OptimizationFinding(
                rule_id, rule["category"], "过度触发关键词", "WARNING", generic,
                "通用词不得单独触发；增加同一条款中的风险表达、缺失字段或结构位置条件。",
            ))
        if context is None:
            findings.append(OptimizationFinding(
                rule_id, rule["category"], "缺少上下文条件", "INFO", [],
                "在 rule_context.json 中补充 required_signals、risk_signals、negative_signals 和审查问题。",
            ))
        else:
            missing = [key for key in ("activation_logic", "required_signals", "risk_signals", "negative_signals") if not context.get(key)]
            if missing:
                findings.append(OptimizationFinding(
                    rule_id, rule["category"], "上下文配置不完整", "WARNING", missing,
                    "补全上下文触发逻辑、正向风险信号和排除信号。",
                ))
        if not self._is_level_score_consistent(rule):
            findings.append(OptimizationFinding(
                rule_id, rule["category"], "风险等级合理性", "WARNING", [str(rule.get("risk_score")), str(rule.get("risk_level"))],
                "使 risk_score 与 HIGH/MIDDLE/LOW 的统一阈值保持一致，或记录业务例外理由。",
            ))
        return findings

    def _load_rules(self) -> list[dict[str, Any]]:
        with self._rules_path.open("r", encoding="utf-8") as file:
            return json.load(file)["rules"]

    def _load_contexts(self) -> list[dict[str, Any]]:
        with self._context_path.open("r", encoding="utf-8") as file:
            return json.load(file)["rules"]

    def _is_level_score_consistent(self, rule: dict[str, Any]) -> bool:
        level = rule.get("risk_level")
        score = rule.get("risk_score")
        if level not in self._level_score_ranges or not isinstance(score, int):
            return False
        lower, upper = self._level_score_ranges[level]
        return lower <= score <= upper
