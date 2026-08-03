"""合同条款提取层：提供面向 LLM 的 JSON 输出框架与确定性回退。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from rule_engine.contract_structure import ContractStructureParser


class ClauseExtractor:
    """将合同文本转换为合同类型、章节、条款和风险提示 JSON。"""

    def __init__(self, structure_parser: ContractStructureParser | None = None) -> None:
        self._structure_parser = structure_parser or ContractStructureParser()

    def extract(self, contract_text: str) -> dict[str, Any]:
        """提取结构化合同信息。

        返回 JSON 兼容字典：`contract_type`、`chapters`、`clauses`、`risk_hints`。

        TODO: 使用 LLM 提取非标准章节、条款、附件和表格中的义务。
        TODO: 让 LLM 识别条款语义、缺失字段和跨条款冲突。
        TODO: 对 LLM JSON 输出进行 schema 校验、纠错与原文定位回查。
        """
        structure = self._structure_parser.parse(contract_text)
        return {
            "contract_type": self._classify(contract_text),
            "title": structure.title,
            "chapters": [
                {
                    "identifier": chapter.identifier,
                    "title": chapter.title,
                    "location": asdict(chapter.location),
                }
                for chapter in structure.chapters
            ],
            "clauses": [
                {
                    "identifier": clause.identifier,
                    "heading": clause.heading,
                    "text": clause.text,
                    "chapter_title": clause.chapter_title,
                    "location": asdict(clause.location),
                }
                for clause in structure.clauses
            ],
            "risk_hints": self._risk_hints(contract_text),
        }

    @staticmethod
    def _classify(text: str) -> str:
        if "软件" in text and ("开发" in text or "服务" in text):
            return "软件开发服务合同"
        return "未分类商业合同"

    @staticmethod
    def _risk_hints(text: str) -> list[str]:
        hints: list[str] = []
        if "另行协商" in text:
            hints.append("存在以另行协商处理核心事项的表述。")
        if "尽快" in text or "适时" in text:
            hints.append("存在难以计算履行期限的模糊时间表述。")
        if "仲裁" in text and "诉讼" in text:
            hints.append("争议解决方式可能存在并列或冲突约定。")
        return hints
