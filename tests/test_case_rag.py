import json
from pathlib import Path

from legal_assistant.case_rag import CaseRAG


CASE_DIR = Path("knowledge_base/cases")
EXPECTED_TYPES = {"民间借贷", "合同纠纷", "劳动争议", "婚姻家庭", "公司纠纷"}
OUTPUT_FIELDS = {"case_name", "court", "case_facts", "judgment_result", "court_opinion", "lawyer_insights"}
REAL_CASE_FIELDS = {
    "case_name", "case_number", "court", "year", "cause", "case_facts", "dispute_issues",
    "first_instance_result", "second_instance_result", "judgment_reason", "legal_basis",
    "lawyer_strategy", "source_level",
}


def test_case_knowledge_base_covers_five_required_categories():
    records = [json.loads(path.read_text(encoding="utf-8")) for path in CASE_DIR.glob("*.json")]

    assert {record["case_type"] for record in records} == EXPECTED_TYPES
    assert all(OUTPUT_FIELDS <= record.keys() for record in records)
    assert all(record["sample_notice"].startswith("脱敏类案") for record in records)


def test_case_rag_retrieves_each_case_category():
    searches = {
        "借款到期不还，有转账和借条": ("借款合同纠纷", "民间借贷"),
        "买卖合同签收后拖欠货款": ("买卖合同纠纷", "合同纠纷"),
        "公司辞退员工且未签劳动合同": ("劳动争议", "劳动争议"),
        "离婚时分割夫妻共同房产": ("婚姻家事纠纷", "婚姻家庭"),
        "股东要求查阅公司会计账簿": ("公司纠纷", "公司纠纷"),
    }

    for query, (case_type, expected) in searches.items():
        result = CaseRAG().search(query, case_type=case_type, top_k=1)
        assert result and result[0].case_type == expected


def test_case_rag_result_exposes_consultation_output_fields():
    result = CaseRAG().search("买卖合同货款逾期", case_type="买卖合同纠纷", top_k=1)[0].as_dict()

    assert OUTPUT_FIELDS <= result.keys()
    assert result["source"].startswith(("internal://", "https://www.court.gov.cn/"))
    assert result["source_level"] in {"A", "C"}
    assert result["score"] > 0


def test_verified_cases_follow_real_case_schema():
    records = [json.loads(path.read_text(encoding="utf-8")) for path in (CASE_DIR / "verified").glob("*.json")]

    assert len(records) >= 2
    assert all(REAL_CASE_FIELDS <= record.keys() for record in records)
    assert all(record["source_level"] == "A" and record["source"].startswith("https://www.court.gov.cn/") for record in records)


def test_case_rag_filters_type_and_returns_similarity_and_trend():
    results = CaseRAG().search("代位权诉讼终结执行后货款未获清偿", case_type="买卖合同纠纷", top_k=5)

    assert results
    assert all(item.case_type == "合同纠纷" for item in results)
    verified = next(item for item in results if item.case_number == "（2019）最高法民终6号")
    assert verified.similarity_analysis
    assert "二审裁判" in verified.judgment_trend
    assert verified.lawyer_strategy
