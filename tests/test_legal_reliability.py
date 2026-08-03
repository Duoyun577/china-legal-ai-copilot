import json

import pytest

from ai.llm_client import LLMResponse
from case_manager import CaseManager, LawyerReviewService
from legal_assistant.case_rag import CaseRAG
from legal_assistant.legal_reference_validator import LegalReferenceValidator
from lawsuit_generator.pleading_service import LitigationPleadingService, PleadingGenerationError


def valid_basis():
    return {
        "legal_basis": "《中华人民共和国民法典》第五百七十七条",
        "law_name": "中华人民共和国民法典",
        "article": "第五百七十七条",
        "legal_text": "当事人一方不履行合同义务的，应当承担违约责任。",
        "source_file": "knowledge_base/laws/civil_code_full.json",
        "source": "国家法律法规数据库",
    }


def test_legal_reference_validator_checks_law_name_and_article():
    validator = LegalReferenceValidator()

    valid = validator.validate(valid_basis())
    missing_law = validator.validate({"law_name": "不存在的法律", "article": "第一条"})
    missing_article = validator.validate({"law_name": "中华人民共和国民法典", "article": "第九千条"})

    assert valid.law_name_exists and valid.article_exists and valid.valid
    assert valid.source_file == "knowledge_base/laws/civil_code_full.json"
    assert not missing_law.law_name_exists and not missing_law.valid
    assert missing_article.law_name_exists and not missing_article.article_exists and not missing_article.valid


def test_case_sources_are_graded_a_b_or_c():
    results = CaseRAG().search("合同逾期未付货款", case_type="合同纠纷", top_k=5)

    assert results
    assert all(item.source_level in {"A", "B", "C"} for item in results)
    assert results[0].source_level == "A"
    assert results[0].source.startswith("https://www.court.gov.cn/")
    assert CaseRAG._source_level({"source": "https://www.court.gov.cn/zixun-xiangqing.html"}) == "A"
    assert CaseRAG._source_level({"source": "https://example.gov.cn/case"}) == "B"


def test_lawyer_review_flow_supports_three_artifact_types(tmp_path):
    manager = CaseManager(tmp_path / "cases.db")
    case = manager.create_case("审核案件", "甲 / 乙", "合同纠纷")
    service = LawyerReviewService(manager)

    consultation = service.confirm(case.case_id, "consultation", "咨询意见可以采用。", status="approved")
    pleading = service.confirm(case.case_id, "pleading", "补充管辖依据。", status="revision_required", artifact_refs=["民事起诉状_法院提交版.docx"])
    contract = service.confirm(case.case_id, "contract_revision", "修订条款审核通过。", status="approved", artifact_refs=["合同_AI修订版.docx"])

    assert consultation.status == "approved"
    assert pleading.status == "revision_required"
    assert contract.artifact_refs == ["合同_AI修订版.docx"]
    assert {item.artifact_type for item in service.list_reviews(case.case_id)} == {
        "consultation", "pleading", "contract_revision",
    }
    assert len([item for item in manager.list_events(case.case_id) if item.event_type == "lawyer_confirmation"]) == 3


class NeverCalledLLM:
    def complete(self, messages, *, response_format="text"):
        raise AssertionError("无效法条应在模型调用前被拒绝")


def test_pleading_rejects_nonexistent_law_before_llm_call():
    invalid = {**valid_basis(), "law_name": "虚构法", "legal_basis": "《虚构法》第五百七十七条"}

    with pytest.raises(PleadingGenerationError, match="法律引用校验失败"):
        LitigationPleadingService(NeverCalledLLM()).generate({
            "verified_legal_basis": [invalid], "verified_similar_cases": [],
        })
