"""法律咨询中的案件事实和争议问题预分析。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CaseIssueAnalysis:
    """进入法条检索前的、可审计的案件问题画像。"""

    facts: list[str]
    case_type: str
    legal_relationships: list[str]
    dispute_issues: list[str]
    supplementary_questions: list[str]
    uncertain_facts: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {key: list(value) if isinstance(value, list) else value for key, value in vars(self).items()}


class CaseIssueAnalyzer:
    """用确定性规则形成检索画像，不依赖现有规则引擎。"""

    _CASE_TYPES = (
        ("劳动争议", ("劳动", "工资", "加班", "辞退", "解雇", "社保")),
        ("婚姻家事纠纷", ("离婚", "抚养", "夫妻", "彩礼", "继承")),
        ("公司纠纷", ("公司", "股东", "股权", "董事", "知情权", "出资")),
        ("侵权责任纠纷", ("侵权", "受伤", "损害", "名誉", "交通事故")),
        ("借款合同纠纷", ("借款", "借钱", "欠款", "还款")),
        ("买卖合同纠纷", ("买卖", "货款", "交货", "产品", "供应")),
        ("合同纠纷", ("合同", "违约", "履行", "解除", "定金")),
    )

    def analyze(self, question: str) -> CaseIssueAnalysis:
        text = question.strip()
        case_type = next((name for name, terms in self._CASE_TYPES if any(term in text for term in terms)), "待判断的民事法律事项")
        facts = [part.strip() for part in re.split(r"[。！？；\n]+", text) if part.strip()][:8] or [text]
        relationships = self._relationships(case_type)
        issues = self._issues(case_type, text)
        questions = self._questions(case_type)
        return CaseIssueAnalysis(facts, case_type, relationships, issues, questions, [item.removesuffix("？") for item in questions])

    @staticmethod
    def _relationships(case_type: str) -> list[str]:
        if case_type == "劳动争议":
            return ["用人单位与劳动者之间的劳动法律关系（主体身份及用工事实待核实）"]
        if case_type == "婚姻家事纠纷":
            return ["婚姻家庭或继承法律关系（当事人身份及亲属关系待核实）"]
        if case_type == "侵权责任纠纷":
            return ["行为人与受损害人之间的侵权责任关系（过错及因果关系待核实）"]
        if case_type == "公司纠纷":
            return ["股东、公司及管理人员之间的公司法律关系（股东资格和争议行为待核实）"]
        if "合同" in case_type:
            return ["当事人之间的合同法律关系（合同成立、生效及履行情况待核实）"]
        return ["当事人之间的民事法律关系尚需结合主体、行为和请求进一步判断"]

    @staticmethod
    def _issues(case_type: str, text: str) -> list[str]:
        if "合同" in case_type:
            issues = ["合同是否成立并生效", "各方是否按约履行及是否构成违约"]
        elif case_type == "劳动争议":
            issues = ["劳动关系是否成立", "用人单位相关行为是否合法"]
        elif case_type == "侵权责任纠纷":
            issues = ["侵权行为、损害后果及因果关系能否证明", "责任主体及责任比例如何认定"]
        elif case_type == "公司纠纷":
            issues = ["公司或股东行为是否符合章程及公司法规定", "相关决议、权利行使或责任承担是否合法"]
        else:
            issues = ["请求权基础、责任主体及构成要件如何认定"]
        if any(term in text for term in ("多久", "时效", "过期")):
            issues.append("相关请求是否超过诉讼时效或除斥期间")
        return issues

    @staticmethod
    def _questions(case_type: str) -> list[str]:
        questions = ["各方主体身份、联系方式及相互关系是什么？", "关键事件发生的具体时间和地点是什么？"]
        if "合同" in case_type:
            questions += ["是否有书面合同、订单、聊天记录或付款凭证？", "约定的履行期限、违约责任及实际履行情况是什么？"]
        elif case_type == "劳动争议":
            questions += ["是否签订劳动合同，入职及离职时间为何？", "工资、考勤、解除通知等证据是否留存？"]
        else:
            questions.append("目前有哪些原始证据可以证明陈述的事实和损失？")
        return questions
