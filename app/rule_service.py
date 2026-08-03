"""本地合同风险规则加载与关键词匹配服务。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuleMatch:
    """一条风险规则的离线匹配结果。"""

    rule_id: str
    category: str
    name: str
    risk_level: str
    risk_score: int
    description: str
    legal_issue: str
    suggestion: str
    matched_keywords: list[str]


class RuleService:
    """读取 contract_rules.json 并对合同文本进行确定性关键词匹配。"""

    def __init__(self, rules_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self._rules_path = rules_path or project_root / "rule_engine" / "contract_rules.json"

    def load_rules(self) -> list[dict[str, Any]]:
        """读取并返回规则库中的规则列表。"""
        with self._rules_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload["rules"]

    def match(self, contract_text: str) -> list[RuleMatch]:
        """基于触发关键词与少量缺失条款启发式发现风险。

        TODO: 接入 LLM 以识别同义表达、否定语义与上下文条件。
        TODO: 使用 RAG 对规则命中结果补充法条与判例依据。
        TODO: 支持条款级定位，而非当前的合同全文匹配。
        """
        matches: list[RuleMatch] = []
        for rule in self.load_rules():
            keywords = [word for word in rule["trigger_keywords"] if word in contract_text]
            if self._matches_missing_clause_risk(rule["rule_id"], contract_text):
                keywords.append("缺失条款启发式")
            if not keywords:
                continue
            matches.append(
                RuleMatch(
                    rule_id=rule["rule_id"],
                    category=rule["category"],
                    name=rule["name"],
                    risk_level=rule["risk_level"],
                    risk_score=rule["risk_score"],
                    description=rule["description"],
                    legal_issue=rule["legal_issue"],
                    suggestion=rule["suggestion"],
                    matched_keywords=keywords,
                )
            )
        return sorted(matches, key=lambda item: (-item.risk_score, item.rule_id))

    @staticmethod
    def _matches_missing_clause_risk(rule_id: str, text: str) -> bool:
        """处理无法仅凭规则关键词表达的明显缺失风险。"""
        return rule_id == "CR-020" and "违约责任" in text and "另行协商" in text
