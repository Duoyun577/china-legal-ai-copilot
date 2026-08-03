"""面向 Contract Review Agent 的法律检索服务门面。"""

from dataclasses import dataclass

from retriever import LegalRetriever, RetrievalQuery, RetrievalResponse


@dataclass
class LegalSearchRequest:
    """合同审查流程传入的检索参数。"""

    risk_description: str
    contract_type: str | None = None
    risk_rule_ids: list[str] | None = None
    top_k: int = 5


class LegalSearchService:
    """将合同风险转换为统一的法律检索请求。"""

    def __init__(self, retriever: LegalRetriever) -> None:
        self._retriever = retriever

    def search_for_review(self, request: LegalSearchRequest) -> RetrievalResponse:
        """为单项合同风险查找可引用法律依据。

        TODO: 接收 review_pipeline.yaml 的风险规则命中结果。
        TODO: 生成查询扩展词并传递合同类型、规则编号等过滤条件。
        TODO: 对输出做法条去重、效力状态核验和引用格式化。
        TODO: 向报告生成器返回法律依据、来源与不确定性说明。
        """
        query = RetrievalQuery(
            query=request.risk_description,
            contract_type=request.contract_type,
            risk_rule_ids=request.risk_rule_ids or [],
            limit=request.top_k,
        )
        return self._retriever.retrieve(query)
