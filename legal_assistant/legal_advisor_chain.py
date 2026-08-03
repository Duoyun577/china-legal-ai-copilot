"""基于案件画像和已核验法律依据生成律师建议。"""

from __future__ import annotations

import json

from ai.llm_client import LLMMessage


class LegalAdvisorChainError(RuntimeError):
    """律师建议链未返回有效的结构化结果。"""


class LegalAdvisorChain:
    REQUIRED_FIELDS = ("risk_warnings", "lawyer_advice")

    def __init__(self, llm_client) -> None:
        self._llm_client = llm_client

    def advise(self, question: str, issue_analysis: dict, legal_basis: list[dict], similar_cases: list[dict] | None = None) -> dict:
        prompt = f"""你是中国执业律师的案件分析辅助工具。请严格输出 JSON，不展示隐含思维过程，只输出可复核的分析结论。
必须按此链路处理：事实抽取、案件类型判断、法律关系分析、争议焦点、补充问题、法律依据、风险提示、律师建议。
顶层字段必须包含：facts、case_type、legal_relationships、dispute_issues、supplementary_questions、legal_basis、similar_cases、risk_warnings、lawyer_advice。
必须参考 verified_similar_cases 中的 similarity_analysis、judgment_trend、lawyer_strategy，解释类案匹配、裁判倾向和可复核的律师策略；不得编造案例或扩大案例结论。
为兼容现有功能还必须包含：question_analysis、recommended_actions、evidence_recommendations、uncertain_facts、lawyer_review_notes。
数组字段必须返回数组。只能使用 verified_legal_basis，不得编造法条或将待核实事实写成确定事实。须提示资料不足、时效、管辖、举证和执行风险，结论须经律师结合原始证据复核。
用户问题：{question}
案件问题画像：{json.dumps(issue_analysis, ensure_ascii=False)}
verified_legal_basis：{json.dumps(legal_basis, ensure_ascii=False)}
verified_similar_cases：{json.dumps(similar_cases or [], ensure_ascii=False)}
"""
        response = self._llm_client.complete([LLMMessage("user", prompt)], response_format="json")
        try:
            result = json.loads(response.content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise LegalAdvisorChainError("模型未返回有效的结构化法律分析。") from exc
        # 旧版咨询响应只有 recommended_actions，升级期间将其视为律师建议。
        if "lawyer_advice" not in result and "recommended_actions" in result:
            result["lawyer_advice"] = result["recommended_actions"]
        missing = [field for field in self.REQUIRED_FIELDS if field not in result]
        if missing:
            raise LegalAdvisorChainError(f"法律分析缺少字段：{', '.join(missing)}")
        return result
