"""融合合同结构、上下文规则与风险评分的 AI 分析层框架。"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from ai.clause_extractor import ClauseExtractor
from ai.llm_client import LLMClient, LLMMessage, MockLLMClient
from rule_engine.risk_scoring import RiskScorer


@dataclass(frozen=True)
class ContextRisk:
    """上下文规则在合同文本中的初步分析结果。"""

    rule_id: str
    triggered: bool
    evidence: list[str]
    risk_score: int
    risk_level: str


class ContractAnalyzer:
    """生成可供 Contract Review 流程消费的 AI 分析结果。"""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        clause_extractor: ClauseExtractor | None = None,
        context_path: Path | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        self._llm_client = llm_client or MockLLMClient()
        self._clause_extractor = clause_extractor or ClauseExtractor()
        self._context_path = context_path or root / "rule_engine" / "rule_context.json"
        self._scorer = RiskScorer()

    def analyze(self, contract_text: str) -> dict[str, Any]:
        """分析合同结构、上下文规则信号和 Mock 模型摘要。

        TODO: 将提示词模板渲染后发送至真实 LLM，并校验结构化响应。
        TODO: 接入 RAG 检索，为每项风险提供现行法条和案例依据。
        TODO: 根据合同金额、行业及完整条款语义动态校准评分参数。
        """
        extraction = self._clause_extractor.extract(contract_text)
        risks = [self._evaluate_context(item, contract_text) for item in self._load_contexts()]
        response = self._llm_client.complete(
            [LLMMessage("user", f"请分析以下合同的法律审查重点：\n{contract_text}")],
            response_format="json",
        )
        return {
            "contract": extraction,
            "context_risks": [asdict(risk) for risk in risks],
            "llm_analysis": {
                "content": response.content,
                "model": response.model,
                "is_mock": response.is_mock,
            },
            "analysis_mode": "mock_offline",
        }

    def _evaluate_context(self, context: dict[str, Any], text: str) -> ContextRisk:
        signals = [signal for signal in context["risk_signals"] if signal in text]
        required = any(signal in text for signal in context["required_signals"])
        triggered = required and len(signals) >= context.get("minimum_evidence_count", 1)
        if triggered:
            score = self._scorer.score(severity=4, impact=4, probability=4, repairability=3)
        else:
            score = self._scorer.score(severity=1, impact=1, probability=1, repairability=5)
        return ContextRisk(
            rule_id=context["rule_id"],
            triggered=triggered,
            evidence=signals,
            risk_score=score.risk_score,
            risk_level=self._scorer.level(score),
        )

    def _load_contexts(self) -> list[dict[str, Any]]:
        with self._context_path.open("r", encoding="utf-8") as file:
            return json.load(file)["rules"]
