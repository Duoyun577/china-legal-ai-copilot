"""为现有 LegalSearchService 提供本地法律库检索适配器。"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


RAG_DIR = Path(__file__).resolve().parents[1] / "rag"
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from legal_search import LegalSearchRequest, LegalSearchService
from retriever import RetrievalResponse
from vector_store import VectorRecord, VectorSearchResult


@dataclass(frozen=True)
class LegalCitation:
    law_name: str
    article: str
    legal_text: str
    source: str
    citation: str
    score: float
    source_file: str = ""


class LocalLawRetriever:
    """按照关键词和规则编号检索项目现有法律 JSON。"""

    def __init__(self, laws_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self._laws_path = laws_path or root / "knowledge_base" / "laws"

    def _load_laws(self) -> list[dict]:
        paths = sorted(self._laws_path.glob("*.json")) if self._laws_path.is_dir() else [self._laws_path]
        laws: list[dict] = []
        root = Path(__file__).resolve().parents[1]
        for path in paths:
            for law in json.loads(path.read_text(encoding="utf-8")):
                record = dict(law)
                record["source_file"] = path.relative_to(root).as_posix()
                laws.append(record)
        return laws

    def retrieve(self, request) -> RetrievalResponse:
        laws = self._load_laws()
        candidates: list[VectorSearchResult] = []
        query = request.query.strip().lower()
        for law in laws:
            score = self._score(law, query, request.risk_rule_ids)
            if score <= 0:
                continue
            record = VectorRecord(record_id=law["law_id"], text=law["legal_text"], embedding=[], metadata=law)
            candidates.append(VectorSearchResult(record=record, score=score))
        candidates.sort(key=lambda item: (-item.score, item.record.record_id))
        return RetrievalResponse(
            results=candidates[: request.limit],
            applied_filters={"source": str(self._laws_path), "contract_type": request.contract_type},
            notes=[] if candidates else ["本地法律库未找到直接匹配条目，请调整关键词或由律师进一步检索。"],
        )

    @staticmethod
    def _score(law: dict, query: str, risk_rule_ids: list[str]) -> float:
        searchable = " ".join(
            [law.get("law_name", ""), law.get("article", ""), law.get("topic", ""), law.get("legal_text", "")]
            + law.get("keywords", [])
        ).lower()
        intent_terms = {term for term in re.split(r"[\s，。；、：/]+", query) if term}
        synonyms = {
            "追款": ("付款", "支付", "履行", "违约", "赔偿"),
            "欠款": ("付款", "支付", "履行", "违约", "赔偿"),
            "逾期": ("期限", "履行", "违约", "赔偿"),
            "解雇": ("解除", "劳动合同", "经济补偿"),
        }
        for trigger, expansions in synonyms.items():
            if trigger in query:
                intent_terms.update(expansions)
        score = 4.0 if query and query in searchable else 0.0
        score += sum(2.0 for keyword in law.get("keywords", []) if keyword.lower() in query)
        score += sum(1.5 for term in intent_terms if len(term) > 1 and term in searchable)
        score += sum(3.0 for rule_id in risk_rule_ids if rule_id in law.get("risk_rules", []))
        return score


class LegalKnowledgeSearch:
    """面向页面和咨询服务的法条检索接口。"""

    def __init__(self, retriever=None) -> None:
        self._service = LegalSearchService(retriever or LocalLawRetriever())

    def search(self, question: str, *, top_k: int = 5) -> list[LegalCitation]:
        response = self._service.search_for_review(LegalSearchRequest(risk_description=question.strip(), top_k=top_k))
        return [
            LegalCitation(
                law_name=result.record.metadata["law_name"],
                article=result.record.metadata["article"],
                legal_text=result.record.text,
                source=self._source_label(result.record.metadata["source"]),
                citation=f"《{result.record.metadata['law_name']}》{result.record.metadata['article']}",
                score=result.score,
                source_file=result.record.metadata.get("source_file", ""),
            )
            for result in response.results
        ]

    @staticmethod
    def _source_label(source: str) -> str:
        if source.startswith("https://flk.npc.gov.cn"):
            return f"国家法律法规数据库：{source}"
        return source
