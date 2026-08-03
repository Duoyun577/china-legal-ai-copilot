"""合同文本的标题、章节、条款与原文定位识别框架。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TextLocation:
    """文本片段在原合同中的字符与行号范围。"""

    start_offset: int
    end_offset: int
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ContractClause:
    """已识别的合同条款。"""

    identifier: str
    heading: str
    text: str
    location: TextLocation
    chapter_title: str | None = None


@dataclass(frozen=True)
class ContractChapter:
    """已识别的合同章节及其所属条款。"""

    identifier: str
    title: str
    location: TextLocation
    clauses: list[ContractClause] = field(default_factory=list)


@dataclass(frozen=True)
class ContractStructure:
    """合同结构化识别结果。"""

    title: str | None
    chapters: list[ContractChapter]
    clauses: list[ContractClause]


class ContractStructureParser:
    """使用常见中文编号规则进行离线合同结构识别。"""

    _chapter_pattern = re.compile(r"^(第[一二三四五六七八九十百]+章\s*.+)$", re.MULTILINE)
    _clause_pattern = re.compile(r"^(第[一二三四五六七八九十百]+条\s*.*)$", re.MULTILINE)

    def parse(self, text: str) -> ContractStructure:
        """解析合同标题、章节、条款，并保存原文定位。

        TODO: 接入 LLM 处理非标准编号、表格条款、附件和扫描件 OCR 文本。
        TODO: 支持款、项、目等更细粒度的层级，以及 DOCX/PDF 原页码定位。
        TODO: 结合合同类型识别模型校正标题与章节语义。
        """
        title = self._find_title(text)
        chapter_matches = list(self._chapter_pattern.finditer(text))
        clause_matches = list(self._clause_pattern.finditer(text))
        chapters = [
            ContractChapter(
                identifier=self._identifier(match.group(1)),
                title=match.group(1).strip(),
                location=self._location(text, match.start(), match.end()),
            )
            for match in chapter_matches
        ]
        clauses = [
            ContractClause(
                identifier=self._identifier(match.group(1)),
                heading=match.group(1).strip(),
                text=text[match.start() : self._next_offset(match, clause_matches, len(text))].strip(),
                location=self._location(text, match.start(), self._next_offset(match, clause_matches, len(text))),
                chapter_title=self._chapter_for_offset(chapters, match.start()),
            )
            for match in clause_matches
        ]
        chapters = [
            ContractChapter(
                identifier=chapter.identifier,
                title=chapter.title,
                location=chapter.location,
                clauses=[clause for clause in clauses if clause.chapter_title == chapter.title],
            )
            for chapter in chapters
        ]
        return ContractStructure(title=title, chapters=chapters, clauses=clauses)

    @staticmethod
    def _find_title(text: str) -> str | None:
        for line in text.splitlines():
            candidate = line.strip()
            if candidate and not candidate.startswith("第"):
                return candidate
        return None

    @staticmethod
    def _identifier(heading: str) -> str:
        return heading.split()[0]

    @staticmethod
    def _next_offset(match: re.Match[str], matches: list[re.Match[str]], default: int) -> int:
        index = matches.index(match)
        return matches[index + 1].start() if index + 1 < len(matches) else default

    @staticmethod
    def _location(text: str, start: int, end: int) -> TextLocation:
        return TextLocation(
            start_offset=start,
            end_offset=end,
            start_line=text.count("\n", 0, start) + 1,
            end_line=text.count("\n", 0, end) + 1,
        )

    @staticmethod
    def _chapter_for_offset(chapters: list[ContractChapter], offset: int) -> str | None:
        eligible = [chapter for chapter in chapters if chapter.location.start_offset <= offset]
        return eligible[-1].title if eligible else None
