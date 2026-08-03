"""上传文件的大小、类型和文件名安全校验。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from config.settings import settings


class FileSecurityError(ValueError):
    """上传文件未通过安全检查。"""


@dataclass(frozen=True)
class SecuredUpload:
    filename: str
    content: bytes
    mime_type: str


_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def secure_filename(filename: str) -> str:
    """移除路径、控制字符和跨平台危险字符，同时保留可读中文名。"""
    basename = PureWindowsPath(str(filename)).name
    basename = Path(basename).name
    basename = _UNSAFE_CHARS.sub("_", basename).strip(" .")
    if not basename:
        raise FileSecurityError("上传文件名无效。")
    path = Path(basename)
    if path.stem.upper() in _WINDOWS_RESERVED:
        basename = f"_{basename}"
    if len(basename) > 180:
        suffix = path.suffix[:20]
        basename = f"{path.stem[:180 - len(suffix)]}{suffix}"
    return basename


def validate_uploaded_file(filename: str, content: bytes, mime_type: str | None = None) -> SecuredUpload:
    safe_name = secure_filename(filename)
    if not content:
        raise FileSecurityError("上传的合同为空，请选择包含正文的合同文件。")
    if len(content) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / (1024 * 1024)
        raise FileSecurityError(f"合同文件超过 {limit_mb:g} MB，请压缩或拆分后重新上传。")
    extension = Path(safe_name).suffix.lower()
    if extension not in settings.allowed_upload_extensions:
        raise FileSecurityError("仅支持 TXT、DOCX 和 PDF 合同。")
    normalized_mime = (mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if normalized_mime not in settings.allowed_upload_mime_types:
        raise FileSecurityError(f"不支持的文件类型：{normalized_mime or '未知'}。")
    return SecuredUpload(safe_name, bytes(content), normalized_mime)
