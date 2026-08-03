"""合同风险评分模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Severity(IntEnum):
    """法律后果严重程度：1 为低，5 为极高。"""

    LOW = 1
    MODERATE = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


@dataclass(frozen=True)
class RiskScore:
    """律师规则模型使用的风险评分字段。"""

    risk_score: int
    severity: int
    impact: int
    probability: int
    repairability: int


class RiskScorer:
    """以严重性、影响、发生概率和可修复性生成 0–100 风险分。"""

    def score(self, *, severity: int, impact: int, probability: int, repairability: int) -> RiskScore:
        """计算风险评分；各输入项必须在 1 至 5 之间。

        较高的严重性、影响和发生概率提高风险；较难修复（较低 repairability）提高风险。

        TODO: 使用历史审查结论和争议结果校准权重。
        TODO: 接入 LLM 识别合同语境后动态评估概率与可修复性。
        TODO: 按合同金额、行业监管和交易角色引入风险系数。
        """
        values = {"severity": severity, "impact": impact, "probability": probability, "repairability": repairability}
        if any(value < 1 or value > 5 for value in values.values()):
            raise ValueError("severity、impact、probability 和 repairability 必须为 1 至 5。")
        raw_score = severity * 0.35 + impact * 0.30 + probability * 0.25 + (6 - repairability) * 0.10
        return RiskScore(
            risk_score=round(raw_score / 5 * 100),
            severity=severity,
            impact=impact,
            probability=probability,
            repairability=repairability,
        )

    @staticmethod
    def level(score: RiskScore) -> str:
        """将数值评分映射为规则库统一的风险等级。"""
        if score.risk_score >= 70:
            return "HIGH"
        if score.risk_score >= 40:
            return "MIDDLE"
        return "LOW"
