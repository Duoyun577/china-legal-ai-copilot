""""China Legal AI Copilot 的 Streamlit 合同审查界面。"""

from __future__ import annotations

import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from io import BytesIO
from pathlib import Path
from ai.providers.deepseek_provider import DeepSeekProviderError
from case_manager import CaseDatabaseBackup, CaseInitializer, CaseManager, EvidenceManager, LawyerReviewService
from case_manager.dashboard import build_lawyer_dashboard
from case_manager.workflow import CaseWorkflow
from contract_review_service import ContractReviewResult, ContractReviewService
from document.contract_rewriter import AIContractRewriter, ContractRewriteError
from document.contract_diff import ContractDiffGenerator
from document.contract_parser import ContractDocumentParser, DocumentParseError
from document.report_generator import ContractReviewReportGenerator
from delivery_center import LitigationPackageError
from legal_assistant.assistant import LegalAssistant, LegalAssistantError
from legal_assistant.case_analysis_report import CaseAnalysisError
from legal_assistant.legal_search_adapter import LegalKnowledgeSearch
from legal_assistant.hearing_assistant import HearingAssistant
from lawyer_memory import LawyerMemory
from lawsuit_generator.civil_complaint import CivilComplaintError, CivilComplaintGenerator
from lawsuit_generator.pleading_service import PleadingGenerationError
from report_service import ReportService
from config.settings import settings
from security.file_security import FileSecurityError, secure_filename, validate_uploaded_file
from utils.logger import initialize_logging, log_exception


logger = initialize_logging()
usage_tracker = UsageTracker()
try:
    _startup_manager = CaseManager()
    CaseDatabaseBackup(_startup_manager.database_path).automatic_backup(
        _startup_manager.database_path.parent / "backups"
    )
except Exception as exc:
    log_exception("automatic_case_database_backup_failed", exc)


RISK_LEVEL_LABELS = {
    "HIGH": "高风险",
    "MIDDLE": "中风险",
    "LOW": "低风险",
}
# 兼容既有调用方；运行时校验仍通过 settings 动态读取环境变量。
MAX_UPLOAD_BYTES = settings.max_upload_bytes


class UploadValidationError(FileSecurityError):
    """上传文件不满足 Web 产品层约束。"""


def get_case_manager() -> CaseManager:
    return CaseManager()


def active_case_id() -> int | None:
    return st.session_state.get("active_case_id")


def show_case_context() -> None:
    case_id = active_case_id()
    if case_id is None:
        st.info("当前未选择案件，本次操作结果不会保存到案件中心。")
        return
    case = get_case_manager().get_case(case_id)
    st.caption(f"当前案件：{case.name}｜{case.parties}｜{case.case_type}")


def render_lawyer_review(artifact_type: str, artifact_refs: list[str], *, key: str, related_analysis: dict | None = None) -> None:
    """为三类法律产物渲染一致的律师审核确认控件。"""
    case_id = active_case_id()
    if case_id is None:
        return
    st.subheader("律师审核确认")
    labels = {"确认通过": "approved", "退回修改": "revision_required", "不予采用": "rejected"}
    label = st.selectbox("审核结论", tuple(labels), key=f"{key}_status")
    opinion = st.text_area("律师审核意见", key=f"{key}_opinion", placeholder="请记录核验结论、修改要求或最终意见。")
    if st.button("保存律师审核记录", key=f"{key}_submit", use_container_width=True):
        try:
            if artifact_type == "consultation":
                LawyerMemory(get_case_manager()).confirm_final_opinion(
                    case_id, opinion, status=labels[label], related_analysis=related_analysis,
                )
            else:
                LawyerReviewService(get_case_manager()).confirm(
                    case_id, artifact_type, opinion, status=labels[label], artifact_refs=artifact_refs,
                    related_analysis=related_analysis,
                )
            st.success("律师审核记录已保存到当前案件。")
        except ValueError as exc:
            st.error(str(exc))


def overall_risk_level(review: ContractReviewResult) -> str:
    """根据现有审查结果计算页面展示的总风险等级。"""
    levels = {risk.risk_level for risk in review.risks}
    if "HIGH" in levels:
        return "HIGH"
    if "MIDDLE" in levels:
        return "MIDDLE"
    return "LOW"


def contract_risk_score(review: ContractReviewResult) -> int:
    """使用现有风险项中的最高分作为 Dashboard 合同风险分。"""
    return max((risk.risk_score for risk in review.risks), default=0)


def risk_level_counts(review: ContractReviewResult) -> dict[str, int]:
    """统计现有风险结果的等级分布。"""
    return {
        level: sum(risk.risk_level == level for risk in review.risks)
        for level in ("HIGH", "MIDDLE", "LOW")
    }


def validate_upload(content: bytes, filename: str = "uploaded_contract.txt", mime_type: str | None = None) -> str:
    try:
        return validate_uploaded_file(filename, content, mime_type).filename
    except FileSecurityError as exc:
        raise UploadValidationError(str(exc)) from exc


def review_uploaded_contract(filename: str, content: bytes) -> tuple[ContractReviewResult, str]:
    """解析上传内容，并通过临时纯文本调用现有审查和报告服务。"""
    safe_name = validate_upload(content, filename)
    parsed = ContractDocumentParser().parse(safe_name, content)
    with TemporaryDirectory(prefix="china_legal_ai_") as temp_dir:
        contract_path = Path(temp_dir) / parsed.filename
        contract_path.write_text(parsed.text, encoding="utf-8")
        review = ContractReviewService().review(contract_path)
        report = ReportService().generate(review)
    return review, report


def generate_download_documents(
    filename: str,
    content: bytes,
    *,
    rewriter: AIContractRewriter | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> tuple[ContractReviewResult, bytes, bytes]:
    """调用现有审查服务并生成建议书与 AI 修订合同两个 DOCX。"""
    safe_name = validate_upload(content, filename)
    notify = progress_callback or (lambda _step, _message: None)
    notify(1, "正在解析合同...")
    parsed = ContractDocumentParser().parse(safe_name, content)
    with TemporaryDirectory(prefix="china_legal_ai_") as temp_dir:
        contract_path = Path(temp_dir) / parsed.filename
        contract_path.write_text(parsed.text, encoding="utf-8")
        notify(2, "正在执行规则检查...")
        notify(3, "正在检索法律依据...")
        review = ContractReviewService().review(contract_path)
        advice_document = ContractReviewReportGenerator().generate(review, parsed.text)
        notify(4, "正在生成AI分析...")
        revised_contract = (rewriter or AIContractRewriter()).rewrite(parsed.text, review)
        notify(5, "生成报告完成")
    return review, advice_document, revised_contract


def ai_revision_summary(revised_contract: bytes) -> str:
    """从生成的 DOCX 中提取供页面预览的修改统计。"""
    document = Document(BytesIO(revised_contract))
    modified = [paragraph.text for paragraph in document.paragraphs if "【AI修改】" in paragraph.text]
    if not modified:
        return "AI 修订合同未标记修改条款。"
    examples = "；".join(item[:80] for item in modified[:3])
    return f"AI 已标记 {len(modified)} 处修改。重点修改示例：{examples}"


def render_dashboard(filename: str, review: ContractReviewResult) -> None:
    """展示合同信息、评分、等级统计与风险分布图。"""
    st.subheader("风险分析 Dashboard")
    st.markdown(f"**合同名称：** {Path(filename).name}  \n**合同类型：** {review.contract_type}")
    counts = risk_level_counts(review)
    level = overall_risk_level(review)
    score_column, level_column, total_column = st.columns(3)
    score_column.metric("合同风险评分", f"{contract_risk_score(review)} / 100")
    level_column.metric("总风险等级", RISK_LEVEL_LABELS[level])
    total_column.metric("风险数量", len(review.risks))

    high_column, middle_column, low_column = st.columns(3)
    high_column.metric("HIGH", counts["HIGH"])
    middle_column.metric("MIDDLE", counts["MIDDLE"])
    low_column.metric("LOW", counts["LOW"])

    chart_data = pd.DataFrame(
        {"风险等级": ["HIGH", "MIDDLE", "LOW"], "数量": [counts["HIGH"], counts["MIDDLE"], counts["LOW"]]}
    ).set_index("风险等级")
    st.markdown("**风险分布图**")
    st.bar_chart(chart_data, horizontal=True, color="#2E74B5")


def render_report_preview(review: ContractReviewResult, revised_contract: bytes) -> None:
    """在下载前展示建议书、TOP 风险和 AI 修订摘要。"""
    st.subheader("报告预览")
    counts = risk_level_counts(review)
    st.markdown(
        f"**审查建议书摘要：** 本次识别 {len(review.risks)} 项风险，其中高风险 {counts['HIGH']} 项、"
        f"中风险 {counts['MIDDLE']} 项、低风险 {counts['LOW']} 项，总体等级为 "
        f"{RISK_LEVEL_LABELS[overall_risk_level(review)]}。"
    )
    st.markdown("**风险 TOP 列表：**")
    for risk in sorted(review.risks, key=lambda item: (-item.risk_score, item.rule_id))[:5]:
        st.markdown(f"- {risk.name}（{risk.rule_id}）：{risk.risk_score} / 100，{RISK_LEVEL_LABELS.get(risk.risk_level, risk.risk_level)}")
    st.markdown(f"**AI 修订摘要：** {ai_revision_summary(revised_contract)}")


def render_risks(review: ContractReviewResult) -> None:
    """展示现有规则引擎返回的风险列表。"""
    if not review.risks:
        st.success("当前规则引擎未发现风险，仍建议由律师人工复核。")
        return

    for index, risk in enumerate(review.risks, start=1):
        label = RISK_LEVEL_LABELS.get(risk.risk_level, risk.risk_level)
        with st.expander(f"{index}. [{label}] {risk.name}（{risk.rule_id}）", expanded=index == 1):
            st.write(risk.description)
            st.markdown(f"**法律问题：** {risk.legal_issue}")
            st.markdown(f"**命中关键词：** {', '.join(risk.matched_keywords)}")
            st.markdown(f"**修改建议：** {risk.suggestion}")


def render_contract_review_page() -> None:
    st.header("合同审查")
    show_case_context()
    st.caption("上传 TXT、DOCX 或文本型 PDF 合同，使用现有规则引擎和本地法律知识库生成合同审查报告。")

    uploaded_file = st.file_uploader(
        "上传合同",
        type=["txt", "docx", "pdf"],
        help="TXT 须为 UTF-8 编码；PDF 须包含可提取的文本层。",
    )
    if uploaded_file is None:
        st.info("请先上传一份 TXT 合同。")
        return

    if st.button("开始审查", type="primary", use_container_width=True):
        try:
            content = uploaded_file.getvalue()
            safe_filename = validate_upload(content, uploaded_file.name, uploaded_file.type)
            with st.status("正在执行合同审查流程...", expanded=True) as process_status:
                def show_progress(step: int, message: str) -> None:
                    process_status.write(f"步骤{step}：{message}")

                with usage_tracker.measure(EVENT_CONTRACT_REVIEW):
                    review, advice_document, revised_contract = generate_download_documents(
                        safe_filename, content, progress_callback=show_progress,
                    )
                original_text = ContractDocumentParser().parse(safe_filename, content).text
                diff_document = ContractDiffGenerator().generate(original_text, revised_contract, review)
                process_status.update(label="合同审查及报告生成完成", state="complete", expanded=False)
            st.session_state["review_outputs"] = {
                "filename": safe_filename,
                "review": review,
                "advice_document": advice_document,
                "revised_contract": revised_contract,
                "diff_document": diff_document,
            }
            if active_case_id() is not None:
                manager = get_case_manager()
                case_id = active_case_id()
                manager.save_file(case_id, "uploaded_contract", safe_filename, content, uploaded_file.type or "application/octet-stream")
                manager.save_file(case_id, "generated_document", f"{Path(safe_filename).stem}_合同风险审查及修改建议书.docx", advice_document, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                manager.save_file(case_id, "generated_document", f"{Path(safe_filename).stem}_AI修订版.docx", revised_contract, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                manager.save_file(case_id, "generated_document", f"{Path(safe_filename).stem}_合同修改说明.docx", diff_document, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                manager.add_record(case_id, "contract_review", f"合同审查：{safe_filename}", {"risk_count": len(review.risks), "overall_level": overall_risk_level(review), "risk_score": contract_risk_score(review)})
                manager.add_event(case_id, "contract_review", f"完成合同审查：{safe_filename}", {"risk_count": len(review.risks)})
        except UploadValidationError as exc:
            st.error(str(exc))
            return
        except DocumentParseError as exc:
            log_exception("contract_document_parse_failed", exc)
            st.error(f"合同读取失败：{exc}")
            return
        except DeepSeekProviderError as exc:
            log_exception("contract_deepseek_request_failed", exc)
            st.error(f"DeepSeek API 调用失败，请检查 API Key、账户余额或网络连接后重试。详细信息：{exc}")
            return
        except ContractRewriteError as exc:
            log_exception("contract_rewrite_failed", exc)
            st.error(f"AI 修订合同生成失败：{exc}")
            return
        except Exception as exc:
            log_exception("contract_review_failed", exc)
            st.error(f"合同审查失败：{exc}")
            return

    outputs = st.session_state.get("review_outputs")
    if not outputs or outputs["filename"] != secure_filename(uploaded_file.name):
        return
    review = outputs["review"]
    safe_filename = outputs["filename"]

    render_dashboard(safe_filename, review)

    st.subheader("风险列表")
    render_risks(review)

    render_report_preview(review, outputs["revised_contract"])

    advice_column, revision_column, diff_column = st.columns(3)
    advice_column.download_button(
        "下载审查建议书",
        data=outputs["advice_document"],
        file_name=f"{Path(safe_filename).stem}_合同风险审查及修改建议书.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )
    revision_column.download_button(
        "下载AI修订合同",
        data=outputs["revised_contract"],
        file_name=f"{Path(safe_filename).stem}_AI修订版.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )
    diff_column.download_button(
        "下载合同修改说明",
        data=outputs["diff_document"],
        file_name=f"{Path(safe_filename).stem}_合同修改说明.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )
    render_lawyer_review(
        "contract_revision",
        [f"{Path(safe_filename).stem}_AI修订版.docx", f"{Path(safe_filename).stem}_合同修改说明.docx"],
        key="contract_revision_review",
        related_analysis={"risk_count": len(review.risks), "overall_level": overall_risk_level(review)},
    )


def render_legal_search_page() -> None:
    st.header("法条检索")
    show_case_context()
    st.caption("输入法律问题关键词，从项目现有法律知识库检索可引用法条。")
    query = st.text_input("法律问题关键词", placeholder="例如：合同违约责任、争议解决、付款期限")
    if st.button("检索法条", type="primary", use_container_width=True):
        if not query.strip():
            st.warning("请输入法律问题关键词。")
            return
        try:
            results = LegalKnowledgeSearch().search(query, top_k=5)
        except Exception as exc:
            log_exception("legal_search_failed", exc)
            st.error(f"法条检索失败，请稍后重试。详细信息：{exc}")
            return
        if not results:
            st.info("本地法律库未找到匹配法条，请尝试更换关键词或由律师进一步检索。")
            return
        st.success(f"找到 {len(results)} 条相关法律依据。")
        if active_case_id() is not None:
            get_case_manager().add_record(
                active_case_id(), "legal_search", f"法条检索：{query.strip()}",
                [{"law_name": item.law_name, "article": item.article, "legal_text": item.legal_text, "source": item.source, "citation": item.citation} for item in results],
            )
            get_case_manager().add_event(active_case_id(), "legal_search", f"法条检索：{query.strip()}", {"result_count": len(results)})
            st.toast("检索结果已保存到当前案件。")
        for item in results:
            with st.container(border=True):
                st.subheader(f"{item.law_name} {item.article}")
                st.write(item.legal_text)
                st.markdown(f"**来源：** {item.source}")
                st.code(item.citation, language=None)


def _render_value(value) -> None:
    if isinstance(value, list):
        for item in value:
            st.markdown(f"- {CivilComplaintGenerator._stringify(item)}")
    else:
        st.write(CivilComplaintGenerator._stringify(value))


def render_legal_assistant_page() -> None:
    st.header("法律咨询")
    show_case_context()
    st.caption("快速咨询使用本地分析与检索；深度律师模式调用 DeepSeek 完成结构化论证。")
    mode_label = st.radio("咨询模式", ("快速咨询", "深度律师"), horizontal=True)
    analysis_mode = "quick" if mode_label == "快速咨询" else "deep"
    question = st.text_area("用户问题", height=160, placeholder="请描述事实背景和需要分析的法律问题。")
    if st.button("生成法律分析", type="primary", use_container_width=True):
        try:
            with st.spinner("正在检索法律依据并生成分析..."):
                with usage_tracker.measure(EVENT_LEGAL_CONSULTATION):
                    st.session_state["legal_analysis"] = LegalAssistant().analyze(question, mode=analysis_mode)
                manager = get_case_manager()
                if active_case_id() is None:
                    initialized = CaseInitializer(manager).initialize(question, st.session_state["legal_analysis"])
                    st.session_state["active_case_id"] = initialized.case_id
                    st.toast(f"已根据首次咨询创建案件：{initialized.name}")
                manager.add_record(active_case_id(), "legal_consultation", f"法律咨询：{question.strip()[:40]}", {"question": question.strip(), "analysis": st.session_state["legal_analysis"]})
                LawyerMemory(manager).remember_consultation(active_case_id(), question, st.session_state["legal_analysis"])
                manager.add_event(active_case_id(), "legal_consultation", "完成法律咨询", {"question": question.strip()[:100]})
        except LegalAssistantError as exc:
            log_exception("legal_consultation_failed", exc)
            st.error(str(exc))
            return
        except DeepSeekProviderError as exc:
            log_exception("legal_consultation_deepseek_failed", exc)
            st.error(f"DeepSeek API 调用失败，请检查 API Key、账户余额或网络连接。详细信息：{exc}")
            return
        except Exception as exc:
            log_exception("legal_consultation_unexpected_failure", exc)
            st.error(f"法律咨询生成失败，请稍后重试。详细信息：{exc}")
            return
    result = st.session_state.get("legal_analysis")
    if not result:
        return
    if result.get("cache_hit"):
        st.caption("已复用缓存分析结果，本次未重复调用模型。")
    st.subheader("案件事实")
    _render_value(result.get("facts", ["待补充"]))
    st.subheader("案件类型判断")
    _render_value(result.get("case_type", "待判断"))
    st.subheader("法律关系分析")
    _render_value(result.get("legal_relationships", ["待进一步分析"]))
    st.subheader("问题分析")
    _render_value(result["question_analysis"])
    st.subheader("法律依据")
    _render_value(result["legal_basis"])
    st.subheader("相似案例")
    similar_cases = result.get("similar_cases", [])
    if not similar_cases:
        st.caption("本地案例库暂未检索到匹配类案。")
    for similar_case in similar_cases:
        st.markdown(f"**类案名称：{similar_case['case_name']}**")
        st.write(f"法院：{similar_case['court']}")
        st.write(f"案件事实：{similar_case['case_facts']}")
        st.write(f"裁判结果：{similar_case['judgment_result']}")
        st.write(f"法院观点：{similar_case['court_opinion']}")
        st.write(f"律师启示：{similar_case['lawyer_insights']}")
        if similar_case.get("case_number"):
            st.write(f"案号：{similar_case['case_number']}｜年份：{similar_case.get('year') or '未公开'}")
        if similar_case.get("similarity_analysis"):
            st.write(f"相似点：{'；'.join(similar_case['similarity_analysis'])}")
        if similar_case.get("judgment_trend"):
            st.write(f"裁判趋势：{similar_case['judgment_trend']}")
        st.write(f"案例来源等级：{similar_case.get('source_level', 'C')}")
        if similar_case.get("sample_notice"):
            st.caption(similar_case["sample_notice"])
    st.subheader("风险提示")
    _render_value(result["risk_warnings"])
    st.subheader("律师建议")
    _render_value(result.get("lawyer_advice", result["recommended_actions"]))
    st.subheader("类案匹配解释")
    _render_value(result.get("case_match_explanations", ["暂无匹配类案"] ))
    st.subheader("裁判倾向")
    _render_value(result.get("judgment_tendency", ["待结合更多类案判断"] ))
    st.subheader("律师策略参考")
    _render_value(result.get("lawyer_strategy_reference", ["由承办律师结合证据制定"] ))
    st.subheader("争议焦点")
    _render_value(result.get("dispute_issues", ["待进一步分析"] ))
    st.subheader("需要补充的问题")
    _render_value(result.get("supplementary_questions", ["待律师进一步询问"]))
    st.subheader("举证建议")
    _render_value(result.get("evidence_recommendations", ["待律师结合证据材料补充"] ))
    st.subheader("不确定事实")
    _render_value(result.get("uncertain_facts", ["待核实"] ))
    st.subheader("律师审核提示")
    _render_value(result.get("lawyer_review_notes", ["本结果须经执业律师审核"] ))
    st.info("本分析为 AI 辅助意见，不替代执业律师结合完整证据出具正式法律意见。")
    render_lawyer_review("consultation", ["当前法律咨询结果"], key="consultation_review", related_analysis=result)
    if active_case_id() is not None and st.button("生成《案件法律分析报告》", use_container_width=True):
        try:
            with st.spinner("正在整理案件事实并生成法律分析报告..."):
                analysis, report = CaseWorkflow(get_case_manager()).generate_case_analysis(active_case_id())
                st.session_state["case_analysis"] = analysis
                st.session_state["case_analysis_report"] = report
            st.success("《案件法律分析报告》已生成并保存到当前案件。")
        except CaseAnalysisError as exc:
            log_exception("case_analysis_failed", exc)
            st.error(str(exc))
        except DeepSeekProviderError as exc:
            log_exception("case_analysis_deepseek_failed", exc)
            st.error(f"DeepSeek API 调用失败，请检查 API Key、账户余额或网络连接。详细信息：{exc}")
    if st.session_state.get("case_analysis_report"):
        st.download_button(
            "下载案件法律分析报告",
            data=st.session_state["case_analysis_report"],
            file_name="案件法律分析报告.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )


def render_lawsuit_generator_page() -> None:
    st.header("文书生成 · 民事起诉状")
    show_case_context()
    st.caption("输入案件事实，使用现有 lawsuit_drafting Prompt 生成待律师复核的 DOCX 初稿。")
    if active_case_id() is not None:
        st.subheader("案件工作流")
        if st.button("生成律师版和法院提交版诉状", type="primary", use_container_width=True):
            try:
                with st.spinner("正在读取案件记忆、法律分析、类案和证据体系..."):
                    with usage_tracker.measure(EVENT_DOCUMENT_GENERATION):
                        st.session_state["case_pleadings"] = CaseWorkflow(get_case_manager()).generate_pleadings_from_case(active_case_id())
                st.success("律师工作版和法院提交版已生成并保存到当前案件。")
            except (ValueError, CivilComplaintError, PleadingGenerationError) as exc:
                log_exception("case_pleading_generation_failed", exc)
                st.error(str(exc))
            except DeepSeekProviderError as exc:
                log_exception("case_pleading_deepseek_failed", exc)
                st.error(f"DeepSeek API 调用失败，请检查 API Key、账户余额或网络连接。详细信息：{exc}")
        if st.session_state.get("case_pleadings"):
            st.download_button(
                "下载律师工作版",
                data=st.session_state["case_pleadings"]["lawyer_version"],
                file_name="民事起诉状_律师工作版.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
            st.download_button(
                "下载法院提交版",
                data=st.session_state["case_pleadings"]["court_version"],
                file_name="民事起诉状_法院提交版.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
            render_lawyer_review(
                "pleading",
                ["民事起诉状_律师工作版.docx", "民事起诉状_法院提交版.docx"],
                key="pleading_review",
            )
        st.divider()
    facts = st.text_area("案件事实", height=260, placeholder="请说明当事人、争议经过、诉讼请求、证据及已知法院信息。")
    if st.button("生成民事起诉状", type="primary", use_container_width=True):
        try:
            with st.spinner("正在生成民事起诉状..."):
                with usage_tracker.measure(EVENT_DOCUMENT_GENERATION):
                    st.session_state["civil_complaint"] = CivilComplaintGenerator().generate(facts)
                if active_case_id() is not None:
                    get_case_manager().save_file(active_case_id(), "generated_document", "民事起诉状_AI初稿.docx", st.session_state["civil_complaint"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    get_case_manager().add_record(active_case_id(), "document_generation", "生成文书：民事起诉状", {"case_facts": facts.strip()})
                    get_case_manager().add_event(active_case_id(), "document_generation", "生成民事起诉状", {})
            st.success("民事起诉状初稿已生成，请下载后由律师复核。")
        except CivilComplaintError as exc:
            log_exception("civil_complaint_generation_failed", exc)
            st.error(str(exc))
            return
        except DeepSeekProviderError as exc:
            log_exception("civil_complaint_deepseek_failed", exc)
            st.error(f"DeepSeek API 调用失败，请检查 API Key、账户余额或网络连接。详细信息：{exc}")
            return
        except Exception as exc:
            log_exception("civil_complaint_unexpected_failure", exc)
            st.error(f"民事起诉状生成失败，请稍后重试。详细信息：{exc}")
            return
    document = st.session_state.get("civil_complaint")
    if document:
        st.download_button(
            "下载民事起诉状 DOCX",
            data=document,
            file_name="民事起诉状_AI初稿.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )


def render_case_center_page() -> None:
    st.header("案件中心")
    manager = get_case_manager()
    with st.form("create_case_form", clear_on_submit=True):
        st.subheader("创建案件")
        name = st.text_input("案件名称")
        parties = st.text_input("当事人", placeholder="例如：甲公司 / 乙公司")
        case_type = st.text_input("案件类型", placeholder="例如：合同纠纷")
        submitted = st.form_submit_button("创建并设为当前案件", type="primary", use_container_width=True)
        if submitted:
            try:
                case = manager.create_case(name, parties, case_type)
                st.session_state["active_case_id"] = case.case_id
                st.success(f"案件“{case.name}”创建成功。")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    case_id = active_case_id()
    if case_id is None:
        st.info("创建或在侧栏选择案件后，可查看该案件的完整工作记录。")
        return
    case = manager.get_case(case_id)
    st.subheader(case.name)
    info_columns = st.columns(3)
    info_columns[0].metric("案件编号", case.case_id)
    info_columns[1].metric("当事人", case.parties)
    info_columns[2].metric("案件类型", case.case_type)

    st.subheader("案件时间线")
    event_labels = {
        "case_created": "创建案件", "legal_consultation": "法律咨询", "legal_search": "法条检索",
        "contract_review": "合同审查", "legal_analysis": "案件分析", "document_generation": "文书生成", "lawyer_confirmation": "律师确认",
        "case_initialization": "案件初始化", "evidence_management": "证据管理", "hearing_preparation": "庭审准备",
        "generated_file": "生成文件",
    }
    for event in manager.list_events(case_id):
        st.markdown(f"**{event.created_at}｜{event_labels.get(event.event_type, event.event_type)}**  \n{event.title}")

    st.subheader("工作记录")
    records = manager.list_records(case_id)
    if not records:
        st.caption("暂无法律咨询、法条检索或文书生成记录。")
    for record in records:
        with st.expander(f"{record.title}｜{record.created_at}"):
            st.json(record.content)

    st.subheader("案件文件")
    files = manager.list_files(case_id)
    if not files:
        st.caption("暂无上传合同或生成文书。")
    for file in files:
        label = "上传合同" if file.category == "uploaded_contract" else "生成文书"
        left, right = st.columns([3, 1])
        left.write(f"{label}｜{file.filename}｜{file.size} bytes｜{file.created_at}")
        right.download_button(
            "下载",
            data=manager.get_file_content(file.file_id),
            file_name=file.filename,
            mime=file.mime_type,
            key=f"case_file_{file.file_id}",
            use_container_width=True,
        )


def render_delivery_center_page() -> None:
    st.header("律师交付材料中心")
    show_case_context()
    case_id = active_case_id()
    if case_id is None:
        st.warning("请先创建或选择案件。")
        return
    manager = get_case_manager()
    analyses = [record for record in manager.list_records(case_id) if record.record_type == "case_legal_analysis"]
    if not analyses:
        st.info("当前案件尚无案件法律分析，请先在法律咨询页面生成《案件法律分析报告》。")
        return
    st.markdown("将根据当前案件信息和最新法律分析生成：民事起诉状、证据目录、证据说明、法律依据清单、诉讼风险分析。")
    if st.button("生成诉讼材料包", type="primary", use_container_width=True):
        try:
            with st.spinner("正在生成五份诉讼交付材料..."):
                with usage_tracker.measure(EVENT_DOCUMENT_GENERATION):
                    st.session_state["litigation_package"] = CaseWorkflow(manager).generate_litigation_package(case_id)
            st.success("诉讼材料包已生成，五份文件均已保存到当前案件并写入时间线。")
        except (ValueError, LitigationPackageError, CivilComplaintError) as exc:
            log_exception("litigation_package_generation_failed", exc)
            st.error(str(exc))
        except DeepSeekProviderError as exc:
            log_exception("litigation_package_deepseek_failed", exc)
            st.error(f"DeepSeek API 调用失败，请检查 API Key、账户余额或网络连接。详细信息：{exc}")
    documents = st.session_state.get("litigation_package", {})
    if documents:
        st.subheader("材料包下载")
        for index, (filename, content) in enumerate(documents.items()):
            st.download_button(
                f"下载 {filename}", data=content, file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"delivery_{index}_{filename}", use_container_width=True,
            )


def navigate_to(page: str) -> None:
    st.session_state["navigation"] = page


def render_evidence_management_page() -> None:
    st.header("证据管理")
    show_case_context()
    case_id = active_case_id()
    if case_id is None:
        st.warning("请先选择案件，或通过首次法律咨询自动创建案件。")
        return
    evidence_manager = EvidenceManager(get_case_manager())
    with st.form("evidence_form"):
        name = st.text_input("证据名称")
        category = st.selectbox("证据分类", sorted(EvidenceManager.CATEGORIES))
        status_label = st.radio("证据状态", ("已有证据", "缺失证据"), horizontal=True)
        purpose = st.text_area("证明目的")
        risk = st.text_area("证据风险", placeholder="例如：仅有复印件、真实性可能被否认、取证期限紧迫。")
        if st.form_submit_button("登记证据", type="primary", use_container_width=True):
            try:
                evidence_manager.add(case_id, name, category, "existing" if status_label == "已有证据" else "missing", purpose, risk)
                st.success("证据已登记并同步到案件长期记忆。")
            except ValueError as exc:
                st.error(str(exc))
    summary = evidence_manager.summarize(case_id)
    existing_column, missing_column = st.columns(2)
    with existing_column:
        st.subheader(f"已有证据（{len(summary.existing)}）")
        for item in summary.existing:
            st.markdown(f"**{item.name}｜{item.category}**  \n证明目的：{item.proof_purpose}  \n风险：{item.risk}")
    with missing_column:
        st.subheader(f"缺失证据（{len(summary.missing)}）")
        for item in summary.missing:
            st.markdown(f"**{item.name}｜{item.category}**  \n证明目的：{item.proof_purpose}  \n风险：{item.risk}")


def render_hearing_assistant_page() -> None:
    st.header("庭审辅助")
    show_case_context()
    case_id = active_case_id()
    if case_id is None:
        st.warning("请先选择案件。")
        return
    if st.button("生成庭审辅助方案", type="primary", use_container_width=True):
        st.session_state["hearing_plan"] = HearingAssistant(get_case_manager()).generate(case_id).as_dict()
    plan = st.session_state.get("hearing_plan")
    if not plan:
        st.info("生成后将展示庭审提纲、询问问题、可能抗辩和应对策略。")
        return
    for heading, field in (
        ("庭审提纲", "hearing_outline"), ("询问问题", "examination_questions"),
        ("对方可能抗辩", "possible_defenses"), ("应对策略", "response_strategies"),
        ("证据风险提示", "evidence_alerts"),
    ):
        st.subheader(heading)
        _render_value(plan[field])


def render_home_page() -> None:
    st.header("律师首页")
    dashboard = build_lawyer_dashboard(get_case_manager())
    case_column, pending_column, file_column, risk_column = st.columns(4)
    case_column.metric("当前案件数量", dashboard.case_count)
    pending_column.metric("待处理事项", len(dashboard.pending_items))
    file_column.metric("最近生成文件", len(dashboard.recent_files))
    risk_column.metric("高风险案件提醒", len(dashboard.risk_reminders))

    st.subheader("快捷操作")
    buttons = st.columns(4)
    buttons[0].button("继续案件分析", on_click=navigate_to, args=("法律咨询",), use_container_width=True)
    buttons[1].button("审查合同", on_click=navigate_to, args=("合同审查",), use_container_width=True)
    buttons[2].button("查询法律", on_click=navigate_to, args=("法条检索",), use_container_width=True)
    buttons[3].button("生成文书", on_click=navigate_to, args=("文书生成",), use_container_width=True)

    recent_column, pending_items_column = st.columns(2)
    with recent_column:
        st.subheader("最近案件")
        if not dashboard.recent_cases:
            st.caption("暂无案件，请前往案件中心创建。")
        for case in dashboard.recent_cases:
            st.markdown(f"**#{case.case_id} {case.name}**  \n{case.parties}｜{case.case_type}｜更新于 {case.updated_at}")
    with pending_items_column:
        st.subheader("待处理事项")
        if not dashboard.pending_items:
            st.caption("暂无待处理事项。")
        for item in dashboard.pending_items:
            st.markdown(f"- #{item.case_id} {item.case_name}：{item.action}")

    st.subheader("案件风险提醒")
    if not dashboard.risk_reminders:
        st.caption("暂无高风险合同审查提醒。")
    for reminder in dashboard.risk_reminders:
        st.error(f"#{reminder.case_id} {reminder.case_name}：{reminder.level}，风险 {reminder.risk_count} 项，评分 {reminder.risk_score}/100")

    st.subheader("最近生成文件")
    if not dashboard.recent_files:
        st.caption("暂无生成文件。")
    manager = get_case_manager()
    for item in dashboard.recent_files:
        left, right = st.columns([3, 1])
        left.write(f"#{item.case_id} {item.case_name}｜{item.file.filename}｜{item.file.created_at}")
        right.download_button(
            "下载", data=manager.get_file_content(item.file.file_id), file_name=item.file.filename,
            mime=item.file.mime_type, key=f"home_file_{item.file.file_id}", use_container_width=True,
        )


def main() -> None:
    st.set_page_config(page_title="China Legal AI Copilot", page_icon="⚖️", layout="wide")
    st.title("China Legal AI Copilot")
    st.sidebar.title("律师工作台")
    manager = get_case_manager()
    cases = manager.list_cases()
    case_options = {"未选择案件": None, **{f"#{case.case_id} {case.name}": case.case_id for case in cases}}
    current_case_id = active_case_id()
    current_label = next((label for label, value in case_options.items() if value == current_case_id), "未选择案件")
    selected_label = st.sidebar.selectbox("当前案件", list(case_options), index=list(case_options).index(current_label))
    st.session_state["active_case_id"] = case_options[selected_label]
    selected_case_id = case_options[selected_label]
    if selected_case_id is None:
        st.session_state.pop("case_memory", None)
    else:
        memory = LawyerMemory(manager).load(selected_case_id, sync=True)
        st.session_state["case_memory"] = memory.as_dict()
        st.sidebar.caption(f"已加载案件记忆：咨询 {len(memory.consultation_history)} 次｜类案 {len(memory.similar_cases)} 个")
    page = st.sidebar.radio(
        "功能导航", ("律师首页", "案件中心", "证据管理", "庭审辅助", "合同审查", "法条检索", "法律咨询", "文书生成", "交付材料中心"),
        key="navigation",
    )
    pages = {
        "律师首页": render_home_page,
        "案件中心": render_case_center_page,
        "证据管理": render_evidence_management_page,
        "庭审辅助": render_hearing_assistant_page,
        "合同审查": render_contract_review_page,
        "法条检索": render_legal_search_page,
        "法律咨询": render_legal_assistant_page,
        "文书生成": render_lawsuit_generator_page,
        "交付材料中心": render_delivery_center_page,
    }
    try:
        pages[page]()
    except Exception as exc:
        log_exception(f"page_render_failed page={page}", exc)
        st.error("页面运行失败，错误详情已写入应用日志，请稍后重试。")


if __name__ == "__main__":
    main()
