"""法律引用的统一结构、提取和来源文件定位。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


LAW_FIELDS = ("law_name", "article", "legal_text", "source_file")


def citation_dict(citation) -> dict[str, str]:
    """将 RAG 返回对象转换为所有 AI 输出共用的引用结构。"""
    return {
        "legal_basis": citation.citation,
        "law_name": citation.law_name,
        "article": citation.article,
        "legal_text": citation.legal_text,
        "source_file": citation.source_file,
        "source": citation.source,
    }


def extract_citations(value) -> list[dict[str, str]]:
    """从已保存的咨询/案件结构中递归提取有效法律引用。"""
    found: list[dict[str, str]] = []
    if isinstance(value, dict):
        if all(isinstance(value.get(field), str) and value[field].strip() for field in LAW_FIELDS):
            found.append({key: str(item) for key, item in value.items() if isinstance(item, str)})
        for item in value.values():
            found.extend(extract_citations(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(extract_citations(item))
    return unique_citations(found)


def unique_citations(citations: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for citation in citations:
        key = (citation.get("law_name", ""), citation.get("article", ""), citation.get("source_file", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(citation)
    return result


def find_source_file(law_name: str, article: str, legal_text: str = "") -> str:
    """根据现有 ContractReviewService 返回值反查知识库来源文件。"""
    root = Path(__file__).resolve().parents[1]
    laws_dir = root / "knowledge_base" / "laws"
    fallback = "knowledge_base/laws/civil_code_contract.json"
    for path in sorted(laws_dir.glob("*.json")):
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if any(
            item.get("law_name") == law_name
            and item.get("article") == article
            and (not legal_text or item.get("legal_text") == legal_text)
            for item in records
        ):
            return path.relative_to(root).as_posix()
    return fallback


def format_citation(citation: dict[str, str]) -> str:
    return (
        f"法律依据：{citation.get('legal_basis') or f'《{citation.get('law_name', '')}》{citation.get('article', '')}'}\n"
        f"法律名称：{citation.get('law_name', '')}\n"
        f"条文编号：{citation.get('article', '')}\n"
        f"条文内容：{citation.get('legal_text', '')}\n"
        f"来源文件：{citation.get('source_file', '')}"
    )


def risk_citations(risk, bases: list, *, legal_search=None, top_k: int = 3) -> list[dict[str, str]]:
    """优先使用规则已关联法条，仅在缺失时通过现有 RAG 补充。"""
    if bases:
        return [
            {
                "legal_basis": f"《{basis.law_name}》{basis.article}",
                "law_name": basis.law_name,
                "article": basis.article,
                "legal_text": basis.legal_text,
                "source_file": find_source_file(basis.law_name, basis.article, basis.legal_text),
                "source": basis.source,
            }
            for basis in bases
        ]
    if legal_search is None:
        from legal_assistant.legal_search_adapter import LegalKnowledgeSearch

        legal_search = LegalKnowledgeSearch()
    query = " ".join((risk.name, risk.description, risk.legal_issue, *risk.matched_keywords))
    return [citation_dict(item) for item in legal_search.search(query, top_k=top_k)]
