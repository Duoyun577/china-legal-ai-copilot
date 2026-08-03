import json
from pathlib import Path


LAW_DIR = Path("knowledge_base/laws")
REQUIRED_FIELDS = {
    "law_id",
    "law_name",
    "article",
    "chapter",
    "topic",
    "legal_text",
    "keywords",
    "applicable_contracts",
    "risk_rules",
    "lawyer_application",
    "source",
}
EXPECTED_LAWS = {
    "civil_code_full.json": (1260, "第一条", "第一千二百六十条"),
    "company_law.json": (266, "第一条", "第二百六十六条"),
    "labor_contract_law.json": (98, "第一条", "第九十八条"),
    "civil_procedure_law.json": (306, "第一条", "第三百零六条"),
    "civil_code_contract_interpretation.json": (69, "第一条", "第六十九条"),
}


def load_law_file(filename: str) -> list[dict]:
    with (LAW_DIR / filename).open(encoding="utf-8") as stream:
        return json.load(stream)


def test_complete_law_files_load_with_expected_article_ranges() -> None:
    for filename, (expected_count, first_article, last_article) in EXPECTED_LAWS.items():
        records = load_law_file(filename)

        assert len(records) == expected_count
        assert records[0]["article"] == first_article
        assert records[-1]["article"] == last_article
        assert len({record["article"] for record in records}) == expected_count
        assert len({record["law_id"] for record in records}) == expected_count


def test_every_law_record_preserves_schema_and_search_metadata() -> None:
    for filename in EXPECTED_LAWS:
        for record in load_law_file(filename):
            assert REQUIRED_FIELDS <= record.keys()
            assert all(isinstance(record[field], str) and record[field].strip() for field in (
                "law_id", "law_name", "article", "chapter", "topic", "legal_text",
                "lawyer_application", "source",
            ))
            assert isinstance(record["keywords"], list) and record["keywords"]
            assert isinstance(record["applicable_contracts"], list) and record["applicable_contracts"]
            assert isinstance(record["risk_rules"], list)
            assert all(rule.startswith("CR-") and len(rule) == 6 for rule in record["risk_rules"])
            assert record["source"].startswith("https://")


def test_law_schema_requires_lawyer_application() -> None:
    schema = json.loads(Path("knowledge_base/schema/law_schema.json").read_text(encoding="utf-8"))

    assert "lawyer_application" in schema["items"]["required"]
    assert schema["items"]["properties"]["lawyer_application"]["type"] == "string"


def test_source_footers_are_not_included_in_legal_text() -> None:
    all_records = [record for filename in EXPECTED_LAWS for record in load_law_file(filename)]

    assert all("相关报道" not in record["legal_text"] for record in all_records)
    assert all("京ICP备" not in record["legal_text"] for record in all_records)
    labor_law = load_law_file("labor_contract_law.json")
    assert labor_law[-1]["legal_text"] == "本法自2008年1月1日起施行。"
