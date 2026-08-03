"""根据本地现行法律知识库校验法律名称和条号。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class CitationValidation:
    law_name: str
    article: str
    law_name_exists: bool
    article_exists: bool
    valid: bool
    source_file: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class LegalReferenceValidator:
    def __init__(self, laws_dir: Path | None = None) -> None:
        self._laws_dir = laws_dir or Path(__file__).resolve().parents[1] / "knowledge_base" / "laws"

    def validate(self, citation: dict) -> CitationValidation:
        law_name = str(citation.get("law_name", "")).strip()
        article = str(citation.get("article", "")).strip()
        index = self._build_index(str(self._laws_dir.resolve()))
        law_name_exists = law_name in index
        article_record = index.get(law_name, {}).get(article)
        return CitationValidation(
            law_name=law_name,
            article=article,
            law_name_exists=law_name_exists,
            article_exists=article_record is not None,
            valid=bool(law_name_exists and article_record),
            source_file=article_record or "",
        )

    def validate_many(self, citations: list[dict], *, strict: bool = False) -> list[dict]:
        results = [self.validate(item).as_dict() for item in citations]
        if strict:
            invalid = [item for item in results if not item["valid"]]
            if invalid:
                labels = ", ".join(f"{item['law_name'] or '【缺失法名】'}{item['article'] or '【缺失条号】'}" for item in invalid)
                raise ValueError(f"法律引用校验失败：{labels}")
        return results

    @staticmethod
    @lru_cache(maxsize=8)
    def _build_index(laws_dir: str) -> dict[str, dict[str, str]]:
        root = Path(laws_dir).parents[1]
        index: dict[str, dict[str, str]] = {}
        for path in sorted(Path(laws_dir).glob("*.json")):
            try:
                records = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for record in records if isinstance(records, list) else []:
                law_name = str(record.get("law_name", "")).strip()
                article = str(record.get("article", "")).strip()
                if law_name and article:
                    index.setdefault(law_name, {})[article] = path.relative_to(root).as_posix()
        return index
