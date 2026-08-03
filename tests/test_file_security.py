import pytest

from security.file_security import FileSecurityError, secure_filename, validate_uploaded_file


def test_secure_filename_removes_paths_and_unsafe_characters() -> None:
    assert secure_filename("../../客户:合同?.txt") == "客户_合同_.txt"
    assert secure_filename(r"C:\fakepath\服务合同.docx") == "服务合同.docx"


def test_upload_rejects_oversized_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "4")
    with pytest.raises(FileSecurityError, match="超过"):
        validate_uploaded_file("contract.txt", b"12345", "text/plain")


@pytest.mark.parametrize("filename,mime_type", [
    ("contract.exe", "application/octet-stream"),
    ("contract.txt", "application/x-msdownload"),
])
def test_upload_rejects_disallowed_extension_or_mime(filename: str, mime_type: str) -> None:
    with pytest.raises(FileSecurityError, match="仅支持|不支持"):
        validate_uploaded_file(filename, b"content", mime_type)


def test_valid_upload_returns_normalized_metadata() -> None:
    upload = validate_uploaded_file("../合同.PDF", b"%PDF-1.7", "application/pdf; charset=binary")
    assert upload.filename == "合同.PDF"
    assert upload.mime_type == "application/pdf"
