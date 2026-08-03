from io import BytesIO
import json
from pathlib import Path
import sys

from docx import Document
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from ai.llm_client import LLMResponse
from legal_assistant.assistant import LegalAssistant, LegalAssistantError
from legal_assistant.legal_search_adapter import LegalCitation, LegalKnowledgeSearch
from lawsuit_generator.civil_complaint import CivilComplaintError, CivilComplaintGenerator


class FakeLLMClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.messages = []

    def complete(self, messages, *, response_format="text") -> LLMResponse:
        self.messages = messages
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False), model="test", is_mock=True)


class FakeLegalSearch:
    def search(self, question: str, *, top_k: int = 5) -> list[LegalCitation]:
        return [
            LegalCitation(
                law_name="中华人民共和国民法典",
                article="第五百七十七条",
                legal_text="当事人一方不履行合同义务的，应当承担违约责任。",
                source="国家法律法规数据库",
                citation="《中华人民共和国民法典》第五百七十七条",
                score=4.0,
                source_file="knowledge_base/laws/civil_code_full.json",
            )
        ]


def test_legal_search_calls_existing_facade_and_returns_citations() -> None:
    results = LegalKnowledgeSearch().search("违约责任", top_k=3)

    assert results
    assert len(results) <= 3
    assert results[0].law_name == "中华人民共和国民法典"
    assert results[0].legal_text
    assert results[0].source.startswith("国家法律法规数据库")
    assert results[0].citation.startswith("《中华人民共和国民法典》")


def test_legal_assistant_returns_required_structure_with_rag_context() -> None:
    payload = {
        "question_analysis": "存在迟延履行问题。",
        "legal_basis": [{"citation": "《中华人民共和国民法典》第五百七十七条"}],
        "risk_warnings": ["证据尚需核实"],
        "recommended_actions": ["发送书面催告"],
        "dispute_issues": ["付款义务是否到期"],
        "evidence_recommendations": ["补充付款凭证"],
        "uncertain_facts": ["付款日期待核实"],
        "lawyer_review_notes": ["核对诉讼时效"],
    }
    client = FakeLLMClient(payload)

    result = LegalAssistant(llm_client=client, legal_search=FakeLegalSearch()).analyze("对方不履行合同怎么办？")

    assert result["question_analysis"] == payload["question_analysis"]
    assert result["legal_basis"] == [{
        "legal_basis": "《中华人民共和国民法典》第五百七十七条",
        "law_name": "中华人民共和国民法典",
        "article": "第五百七十七条",
        "legal_text": "当事人一方不履行合同义务的，应当承担违约责任。",
        "source_file": "knowledge_base/laws/civil_code_full.json",
        "source": "国家法律法规数据库",
    }]
    assert "第五百七十七条" in client.messages[0].content


def test_legal_assistant_rejects_empty_question() -> None:
    with pytest.raises(LegalAssistantError, match="请输入"):
        LegalAssistant(llm_client=FakeLLMClient({}), legal_search=FakeLegalSearch()).analyze("  ")


def test_civil_complaint_uses_existing_prompt_and_outputs_docx() -> None:
    payload = {
        "document_type": "起诉状初稿",
        "court": "【待确认有管辖权的人民法院】",
        "parties": [{"原告": "【待填写】"}, {"被告": "【待填写】"}],
        "claims": ["请求判令被告支付欠款【待核实金额】"],
        "facts_and_reasons": ["双方存在合同关系，具体证据待核实。"],
        "evidence_list": ["合同及付款凭证"],
        "legal_basis": ["《中华人民共和国民法典》相关规定，具体条文待核验"],
        "procedural_uncertainties": ["管辖法院待核实"],
        "lawyer_review_required": True,
    }
    client = FakeLLMClient(payload)

    content = CivilComplaintGenerator(llm_client=client, legal_search=FakeLegalSearch()).generate("被告拖欠合同款，原告拟起诉。")
    document = Document(BytesIO(content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert content.startswith(b"PK")
    assert "民事起诉状" in text
    assert "诉讼请求" in text
    assert "事实与理由" in text
    assert "相关法律依据建议" in text
    assert "法律名称：中华人民共和国民法典" in text
    assert "条文编号：第五百七十七条" in text
    assert "来源文件：knowledge_base/laws/civil_code_full.json" in text
    assert "律师审核" in text
    assert "中国民事合同纠纷起诉材料 Prompt" in client.messages[0].content


def test_civil_complaint_rejects_empty_facts() -> None:
    with pytest.raises(CivilComplaintError, match="请输入案件事实"):
        CivilComplaintGenerator(llm_client=FakeLLMClient({})).generate(" ")
