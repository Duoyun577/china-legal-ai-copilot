"""将内部结构化字段转换为适合中文法律文书展示的文本。"""

from __future__ import annotations

import re


FIELD_LABELS = {
    "law_name": "法律名称",
    "article": "条文编号",
    "basis_text": "依据内容",
    "legal_text": "条文内容",
    "legal_basis": "法律依据",
    "source": "来源",
    "source_file": "来源文件",
    "note": "适用说明",
    "number": "序号",
    "name": "名称",
    "title": "标题",
    "type": "类型",
    "content": "内容",
    "purpose": "证明目的",
    "status": "状态",
    "risk": "风险",
    "suggestion": "建议",
    "court": "法院",
    "case_number": "案号",
    "date": "日期",
    "url": "链接",
    "facts": "事实",
    "reason": "理由",
    "claims": "诉讼请求",
    "parties": "当事人",
    "evidence": "证据",
}

_ASCII_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_CHINESE = re.compile(r"[\u3400-\u9fff]")


def chinese_field_label(key: object) -> str | None:
    """返回中文展示标签；未知英文内部字段不直接暴露给文书。"""
    text = str(key).strip()
    if not text:
        return None
    label = FIELD_LABELS.get(text.lower())
    if label:
        return label
    if _CHINESE.search(text):
        return text
    if _ASCII_FIELD.fullmatch(text):
        return None
    return text


def stringify_chinese(value: object) -> str:
    """递归格式化数据，翻译已知字段并隐藏未知英文内部键名。"""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            rendered = stringify_chinese(item)
            if not rendered:
                continue
            label = chinese_field_label(key)
            parts.append(f"{label}：{rendered}" if label else rendered)
        return "；".join(parts)
    if isinstance(value, (list, tuple, set)):
        return "；".join(filter(None, (stringify_chinese(item) for item in value)))
    return "" if value is None else str(value)
