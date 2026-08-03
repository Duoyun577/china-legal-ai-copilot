"""案件咨询、法律分析与诉讼文书的自动流转。"""

from __future__ import annotations

import json

from case_manager.repository import CaseManager
from delivery_center.litigation_package import LitigationPackageGenerator
from legal_assistant.case_analysis_report import CaseLegalAnalysisReportGenerator
from legal_assistant.analysis_cache import AnalysisCache
from legal_assistant.citation_utils import extract_citations
from legal_assistant.legal_search_adapter import LegalKnowledgeSearch
from lawyer_memory import LawyerMemory
from lawsuit_generator.civil_complaint import CivilComplaintGenerator
from lawsuit_generator.pleading_service import LitigationPleadingService


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class CaseWorkflow:
    def __init__(
        self,
        manager: CaseManager,
        *,
        analysis_generator: CaseLegalAnalysisReportGenerator | None = None,
        complaint_generator: CivilComplaintGenerator | None = None,
        package_generator: LitigationPackageGenerator | None = None,
        memory: LawyerMemory | None = None,
        pleading_service: LitigationPleadingService | None = None,
        analysis_cache: AnalysisCache | None = None,
    ) -> None:
        self._manager = manager
        self._analysis_generator = analysis_generator or CaseLegalAnalysisReportGenerator()
        self._complaint_generator = complaint_generator
        self._pleading_service = pleading_service or (LitigationPleadingService() if complaint_generator is None else None)
        self._package_generator = package_generator or LitigationPackageGenerator()
        self._memory = memory or LawyerMemory(manager)
        self._analysis_cache = analysis_cache or AnalysisCache(manager.database_path)

    def generate_case_analysis(self, case_id: int) -> tuple[dict, bytes]:
        case = self._manager.get_case(case_id)
        consultations = [record for record in self._manager.list_records(case_id) if record.record_type == "legal_consultation"]
        cache_payload = {
            "case": {"name": case.name, "parties": case.parties, "case_type": case.case_type},
            "consultations": [{"title": item.title, "content": item.content, "created_at": item.created_at} for item in consultations],
            "schema": "final-011-e-v1",
        }
        analysis = self._analysis_cache.get("case_analysis", cache_payload)
        cache_hit = analysis is not None
        if not cache_hit:
            analysis = self._reuse_consultation_analysis(consultations)
            if analysis is not None:
                document = CaseLegalAnalysisReportGenerator._build_docx(case, analysis)
            else:
                analysis, document = self._analysis_generator.generate(case, consultations)
            self._analysis_cache.set("case_analysis", cache_payload, analysis)
        else:
            document = CaseLegalAnalysisReportGenerator._build_docx(case, analysis)
        self._manager.add_record(case_id, "case_legal_analysis", "案件法律分析报告", analysis)
        self._memory.remember_analysis(case_id, analysis)
        self._manager.save_file(case_id, "generated_document", "案件法律分析报告.docx", document, DOCX_MIME)
        self._manager.add_event(case_id, "legal_analysis", "生成案件法律分析报告", {"consultation_count": len(consultations), "cache_hit": cache_hit})
        return analysis, document

    @staticmethod
    def _reuse_consultation_analysis(consultations: list) -> dict | None:
        """将完整咨询结果直接转换成案件分析，避免重复模型请求。"""
        for record in consultations:
            content = record.content if isinstance(record.content, dict) else {}
            source = content.get("analysis") if isinstance(content.get("analysis"), dict) else {}
            required = ("facts", "legal_relationships", "dispute_issues", "legal_basis", "risk_warnings", "lawyer_advice")
            if not all(source.get(field) for field in required):
                continue
            return {
                "case_facts": source["facts"],
                "legal_relationships": source["legal_relationships"],
                "dispute_issues": source["dispute_issues"],
                "legal_basis": source["legal_basis"],
                "risk_analysis": source["risk_warnings"],
                "litigation_strategy": source["lawyer_advice"],
                "next_steps": source.get("recommended_actions", source["lawyer_advice"]),
                "similar_cases": source.get("similar_cases", []),
                "source": "legal_consultation_reuse",
            }
        return None

    def generate_complaint_from_case(self, case_id: int) -> bytes:
        if self._pleading_service is not None:
            return self.generate_pleadings_from_case(case_id)["court_version"]
        case = self._manager.get_case(case_id)
        records = self._manager.list_records(case_id)
        consultations = [record.content for record in records if record.record_type == "legal_consultation"]
        analyses = [record.content for record in records if record.record_type == "case_legal_analysis"]
        if not analyses:
            raise ValueError("当前案件尚无案件法律分析报告，请先生成案件分析。")
        context = {
            "案件信息": {"案件名称": case.name, "当事人": case.parties, "案件类型": case.case_type},
            "法律咨询记录": consultations,
            "案件法律分析": analyses[0],
            "案件长期记忆": self._memory.load(case_id, sync=True).as_dict(),
        }
        document = self._complaint_generator.generate(json.dumps(context, ensure_ascii=False))
        self._manager.save_file(case_id, "generated_document", "基于案件分析_民事起诉状.docx", document, DOCX_MIME)
        self._manager.add_record(case_id, "document_generation", "根据案件分析生成起诉状", {"analysis_used": True})
        self._manager.add_event(case_id, "document_generation", "根据案件分析生成起诉状", {})
        return document

    def generate_pleadings_from_case(self, case_id: int) -> dict[str, bytes]:
        """生成律师工作版和法院提交版；法院版保持正式、无 AI 标识。"""
        if self._pleading_service is None:
            raise ValueError("当前工作流未配置双版本诉状生成服务。")
        context = self._build_pleading_context(case_id)
        documents = self._pleading_service.generate(context)
        result = {"lawyer_version": documents.lawyer_version, "court_version": documents.court_version}
        filenames = {
            "lawyer_version": "民事起诉状_律师工作版.docx",
            "court_version": "民事起诉状_法院提交版.docx",
        }
        for key, content in result.items():
            self._manager.save_file(case_id, "generated_document", filenames[key], content, DOCX_MIME)
        self._manager.add_record(
            case_id, "document_generation", "生成双版本民事起诉状",
            {"versions": list(filenames.values()), "memory_used": True, "analysis_chain": [
                "案件记忆", "案件分析", "案由判断", "争议焦点", "诉讼请求", "法律依据", "类案参考", "证据体系", "生成诉状",
            ]},
        )
        self._manager.add_event(case_id, "document_generation", "生成双版本民事起诉状", {"version_count": 2})
        return result

    def _build_pleading_context(self, case_id: int) -> dict:
        case = self._manager.get_case(case_id)
        records = self._manager.list_records(case_id)
        consultations = [record.content for record in records if record.record_type == "legal_consultation"]
        analyses = [record.content for record in records if record.record_type == "case_legal_analysis"]
        if not analyses:
            raise ValueError("当前案件尚无案件法律分析报告，请先生成案件分析。")
        memory = self._memory.load(case_id, sync=True)
        legal_basis = extract_citations({"memory": memory.as_dict(), "consultations": consultations, "analysis": analyses[0]})
        if not legal_basis:
            query = json.dumps({"case": case.name, "type": case.case_type, "analysis": analyses[0]}, ensure_ascii=False)
            from legal_assistant.citation_utils import citation_dict

            legal_basis = [citation_dict(item) for item in LegalKnowledgeSearch().search(query, top_k=5)]
        return {
            "案件信息": {"案件名称": case.name, "当事人": case.parties, "案件类型": case.case_type},
            "案件长期记忆": memory.as_dict(),
            "法律咨询结果": consultations,
            "案件法律分析": analyses[0],
            "verified_legal_basis": legal_basis,
            "verified_similar_cases": memory.similar_cases,
        }

    def generate_litigation_package(self, case_id: int) -> dict[str, bytes]:
        case = self._manager.get_case(case_id)
        records = self._manager.list_records(case_id)
        analyses = [record.content for record in records if record.record_type == "case_legal_analysis"]
        if not analyses:
            raise ValueError("当前案件尚无案件法律分析报告，请先完成法律分析。")
        documents = self._package_generator.generate(case, analyses[0], records)
        for filename, content in documents.items():
            self._manager.save_file(case_id, "generated_document", filename, content, DOCX_MIME)
        self._manager.add_record(
            case_id, "delivery_package", "生成诉讼材料包", {"files": list(documents)}
        )
        self._manager.add_event(
            case_id, "document_generation", "生成律师诉讼材料包", {"file_count": len(documents)}
        )
        return documents
