"""基于案件记忆和证据状态生成庭审辅助方案。"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from case_manager.evidence import EvidenceManager
from case_manager.repository import CaseManager
from lawyer_memory import LawyerMemory


@dataclass(frozen=True)
class HearingPlan:
    hearing_outline: list[str]
    examination_questions: list[str]
    possible_defenses: list[str]
    response_strategies: list[str]
    evidence_alerts: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


class HearingAssistant:
    def __init__(self, manager: CaseManager) -> None:
        self._manager = manager

    def generate(self, case_id: int) -> HearingPlan:
        case = self._manager.get_case(case_id)
        memory = LawyerMemory(self._manager).load(case_id, sync=True)
        evidence = EvidenceManager(self._manager).summarize(case_id)
        issues = [str(item) for item in memory.dispute_issues] or ["请求权基础及构成要件"]
        outline = [
            f"核对当事人身份、代理权限及案由：{case.case_type}",
            "陈述诉讼请求及其事实、法律依据和计算方式",
            *[f"围绕争议焦点举证、质证并发表意见：{issue}" for issue in issues],
            "归纳争议焦点并发表辩论意见和最后陈述",
        ]
        questions = [f"针对“{issue}”，对方主张的事实依据和原始证据是什么？" for issue in issues]
        questions += [f"请说明证据“{item.name}”的形成时间、来源、保管及原件情况。" for item in evidence.existing]
        defenses = [
            "对方可能否认关键事实或合同关系成立",
            "对方可能主张已履行、抵销、免责或责任减轻",
            "对方可能提出诉讼时效、管辖或主体资格抗辩",
        ]
        strategies = [
            "按争议焦点建立事实—证据—法律依据对应表",
            "对否认真实性的证据准备原件、形成过程和补强材料",
            "提前核对时效中断、管辖连接点及主体资格证据",
        ]
        alerts = [f"缺失证据：{item.name}；证明目的：{item.proof_purpose}；风险：{item.risk}" for item in evidence.missing]
        alerts += [f"已有证据风险：{item.name}—{item.risk}" for item in evidence.existing if item.risk]
        plan = HearingPlan(outline, questions, defenses, strategies, alerts or ["尚未登记证据，请先完成证据清单和缺失证据核查。"])
        self._manager.add_record(case_id, "hearing_plan", "庭审辅助方案", plan.as_dict())
        self._manager.add_event(case_id, "hearing_preparation", "生成庭审辅助方案", {"issue_count": len(issues)})
        return plan
