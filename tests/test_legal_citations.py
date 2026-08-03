from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from contract_review_service import ContractReviewService
from legal_assistant.citation_utils import LAW_FIELDS, risk_citations
from legal_assistant.legal_search_adapter import LegalKnowledgeSearch


def test_rag_citations_include_law_article_text_and_source_file() -> None:
    citations = LegalKnowledgeSearch().search("劳动合同解除经济补偿", top_k=5)

    assert citations
    assert any(citation.law_name == "中华人民共和国劳动合同法" for citation in citations)
    for citation in citations:
        assert citation.law_name
        assert citation.article
        assert citation.legal_text
        assert citation.source_file.startswith("knowledge_base/laws/")


def test_every_contract_risk_has_verified_or_rag_supplemented_citation() -> None:
    review = ContractReviewService().review(
        Path("evaluation/test_contracts/software_service_contract.txt")
    )

    references = {
        risk.rule_id: risk_citations(
            risk, review.legal_basis_by_rule.get(risk.rule_id, [])
        )
        for risk in review.risks
    }

    assert references
    assert all(references.values())
    assert all(
        all(isinstance(item.get(field), str) and item[field].strip() for field in LAW_FIELDS)
        for items in references.values()
        for item in items
    )
