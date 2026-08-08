"""China Legal AI Copilot 离线合同审查命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.contract_review_service import ContractReviewService
from app.report_service import ReportService
from analytics.usage_tracker import EVENT_CONTRACT_REVIEW, UsageTracker
from utils.logger import initialize_logging, log_exception


logger = initialize_logging()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行离线合同审查并生成 Markdown 报告。")
    parser.add_argument("contract_path", type=Path, help="待审查的 UTF-8 文本合同路径")
    parser.add_argument("--output", "-o", type=Path, default=Path("contract_review_report.md"), help="报告输出路径")
    return parser


def main() -> int:
    """执行读取合同、规则匹配、法律依据关联与报告生成。"""
    args = build_parser().parse_args()
    if not args.contract_path.is_file():
        raise SystemExit(f"合同文件不存在：{args.contract_path}")
    try:
        with UsageTracker().measure(EVENT_CONTRACT_REVIEW):
            review = ContractReviewService().review(args.contract_path)
            report = ReportService().generate(review)
    except Exception as exc:
        log_exception("cli_contract_review_failed", exc)
        raise
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"已生成审查报告：{args.output}")
    print(f"匹配风险数量：{len(review.risks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
