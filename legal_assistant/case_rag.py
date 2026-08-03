"""独立于 RAG 核心的结构化真实案例检索适配器。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SimilarCase:
    case_id: str
    case_name: str
    case_number: str
    court: str
    year: int | None
    case_type: str
    cause: str
    case_facts: str
    dispute_issues: list[str]
    first_instance_result: str
    second_instance_result: str
    judgment_reason: str
    legal_basis: list[str]
    lawyer_strategy: list[str]
    source: str
    source_level: str
    score: float
    similarity_analysis: list[str]
    judgment_trend: str
    judgment_result: str
    court_opinion: str
    lawyer_insights: str
    sample_notice: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class CaseRAG:
    """按案由过滤，并对案例事实、争点、理由和法律依据进行确定性召回。"""

    REQUIRED_FIELDS = (
        "case_name", "case_number", "court", "year", "cause", "case_facts",
        "dispute_issues", "first_instance_result", "second_instance_result",
        "judgment_reason", "legal_basis", "lawyer_strategy", "source_level", "source",
    )
    _TYPE_ALIASES = {
        "借款合同纠纷": "民间借贷", "婚姻家事纠纷": "婚姻家庭",
        "买卖合同纠纷": "合同纠纷", "确认劳动关系纠纷": "劳动争议",
    }

    def __init__(self, cases_dir: Path | None = None) -> None:
        self._cases_dir = cases_dir or Path(__file__).resolve().parents[1] / "knowledge_base" / "cases"

    def search(self, query: str, *, case_type: str = "", top_k: int = 3) -> list[SimilarCase]:
        if top_k < 1:
            return []
        expected_type = self._TYPE_ALIASES.get(case_type, case_type)
        candidates = []
        for raw_record in self._load_cases():
            record = self._normalize(raw_record)
            if expected_type and not self._type_matches(expected_type, record["case_type"]):
                continue
            score, matches = self._score(record, query, expected_type)
            if score <= 0:
                continue
            candidates.append(SimilarCase(
                **{field: record[field] for field in (
                    "case_id", "case_name", "case_number", "court", "year", "case_type", "cause",
                    "case_facts", "dispute_issues", "first_instance_result", "second_instance_result",
                    "judgment_reason", "legal_basis", "lawyer_strategy", "source", "source_level",
                    "judgment_result", "court_opinion", "lawyer_insights", "sample_notice",
                )},
                score=score,
                similarity_analysis=matches or [f"案由同为{record['cause']}"],
                judgment_trend=self._judgment_trend(record),
            ))
        return sorted(candidates, key=lambda item: (-item.score, -(item.year or 0), item.case_id))[:top_k]

    def _load_cases(self) -> list[dict]:
        records = []
        for path in sorted(self._cases_dir.rglob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data if isinstance(data, list) else [data]:
                if not isinstance(item, dict):
                    raise ValueError(f"案例文件 {path.name} 的条目必须是对象。")
                records.append(item)
        return records

    @classmethod
    def _normalize(cls, item: dict) -> dict:
        # Final-013-A-3 前的脱敏样本按旧字段兼容，不伪造案号、年份和审级信息。
        real_case = all(field in item for field in cls.REQUIRED_FIELDS)
        record = {
            "case_id": str(item.get("case_id") or item.get("case_number") or ""),
            "case_name": str(item.get("case_name", "")),
            "case_number": str(item.get("case_number", "未公开（脱敏样本）")),
            "court": str(item.get("court", "")),
            "year": item.get("year") if isinstance(item.get("year"), int) else None,
            "case_type": str(item.get("case_type") or item.get("cause", "")),
            "cause": str(item.get("cause") or item.get("case_type", "")),
            "case_facts": str(item.get("case_facts", "")),
            "dispute_issues": cls._list(item.get("dispute_issues", [])),
            "first_instance_result": str(item.get("first_instance_result") or item.get("judgment_result", "")),
            "second_instance_result": str(item.get("second_instance_result", "未公开或不适用")),
            "judgment_reason": str(item.get("judgment_reason") or item.get("court_opinion", "")),
            "legal_basis": cls._list(item.get("legal_basis", [])),
            "lawyer_strategy": cls._list(item.get("lawyer_strategy") or item.get("lawyer_insights", "")),
            "keywords": cls._list(item.get("keywords", [])),
            "source": str(item.get("source", "")),
            "source_level": cls._source_level(item),
            "sample_notice": str(item.get("sample_notice", "")),
        }
        required_text = ("case_id", "case_name", "court", "case_type", "case_facts", "judgment_reason", "source")
        missing = [field for field in required_text if not record[field]]
        if missing:
            raise ValueError(f"案例条目缺少字段：{', '.join(missing)}")
        record["judgment_result"] = "；".join(filter(None, (record["first_instance_result"], record["second_instance_result"])))
        record["court_opinion"] = record["judgment_reason"]
        record["lawyer_insights"] = "；".join(record["lawyer_strategy"])
        record["is_real_case"] = real_case
        return record

    @staticmethod
    def _source_level(record: dict) -> str:
        explicit = str(record.get("source_level", "")).upper()
        if explicit in {"A", "B", "C"}:
            return explicit
        source = str(record.get("source", "")).lower()
        return "A" if "court.gov.cn" in source else "B" if "gov.cn" in source or "chinacourt.org" in source else "C"

    @classmethod
    def _type_matches(cls, expected: str, actual: str) -> bool:
        actual_normalized = cls._TYPE_ALIASES.get(actual, actual)
        return expected == actual_normalized or expected in actual_normalized or actual_normalized in expected

    @staticmethod
    def _score(record: dict, query: str, expected_type: str) -> tuple[float, list[str]]:
        normalized_query = query.lower().strip()
        terms = {term for term in re.split(r"[\s，。；、：/！？]+", normalized_query) if len(term) > 1}
        score = 12.0 if expected_type else 0.0
        matches = []
        for keyword in record["keywords"]:
            if str(keyword).lower() in normalized_query:
                score += 4.0
                matches.append(f"共同关键词：{keyword}")
        fields = ("case_name", "cause", "case_facts", "judgment_reason")
        searchable = " ".join(str(record[field]) for field in fields)
        searchable += " " + " ".join(record["dispute_issues"] + record["legal_basis"])
        for term in terms:
            if term in searchable.lower():
                score += 1.0
                matches.append(f"事实或争点相似：{term}")
        return score, list(dict.fromkeys(matches))[:5]

    @staticmethod
    def _judgment_trend(record: dict) -> str:
        if record["second_instance_result"] and record["second_instance_result"] != "未公开或不适用":
            return f"二审裁判：{record['second_instance_result']}"
        return f"已公开裁判结果：{record['first_instance_result']}"

    @staticmethod
    def _list(value) -> list[str]:
        if value is None:
            return []
        return [str(item) for item in value] if isinstance(value, list) else [str(value)]
