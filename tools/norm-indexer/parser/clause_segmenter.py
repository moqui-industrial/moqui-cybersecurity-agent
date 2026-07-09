from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SegmentedClause:
    clause_number: str
    title: str
    text: str
    start_line: int
    end_line: int
    parent_clause_number: str | None
    provenance_class: str
    diagnostics: list[str] = field(default_factory=list)


_PAGE_MARKER_RE = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")
_DOT_LEADER_RE = re.compile(r"\.{3,}")
_NUMBERED_LIST_HEADING_RE = re.compile(r"^\s*(\d{1,3})\.\s+(\S.*)$")
_EN_IEC_HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,4}|[A-Z]{1,2}\.\d+(?:\.\d+){0,4})\s+([A-Za-zÀ-ɏ].*)$")
# Annex/Allegato heading for the en-iec-hierarchical family (IEC 62443-*, EN 40000-*). Real data
# checked before writing this regex (pdftotext on the actual PDFs, not assumed): clean documents
# have a space ("Annex A", IEC 62443-4-2/3-3), but both EN 40000-1-2/1-3 are OCR'd
# (ocrSource=true in norm-sources.json) and their real body headings have NO space
# ("AnnexA", "AnnexZA") - a naive `\s+` separator would silently miss every Annex in both OCR'd
# documents. `\s*` (zero-or-more) handles both. The designator itself is matched
# case-SENSITIVELY (only the "Annex"/"Allegato" word is case-insensitive, via the scoped `(?i:)`
# group) specifically so a real word like "Annexation" starting a body line can never match - its
# tail is lowercase, `[A-Z]` requires uppercase, so it fails while a real "AnnexZA"/"Annex A" (its
# designator always capitalized in every real document checked) still matches.
_EN_IEC_ANNEX_RE = re.compile(r"^\s*(?i:Annex|Allegato)\s*([A-Z]{1,2}[A-Z0-9]{0,3})\b(?:[\s\-:]+(\S.*))?$")
_ARTICLE_HEADING_RE = re.compile(r"^\s*(?:Articolo|Article)\s+(\d+)\s*$", re.IGNORECASE)
# Annex/Allegato heading for the eu-regulation-article family. Real data checked (Machinery Reg.,
# CRA, NIS2 PDFs): all three use clean, properly-spaced "ALLEGATO I".."ALLEGATO XII" / "ANNEX
# I".."ANNEX III" - no OCR artifacts in this family (none of these 3 documents are ocrSource),
# so a plain `\s+` separator is correct here (unlike the en-iec-hierarchical family above).
_ANNEX_HEADING_RE = re.compile(r"^\s*(?:Allegato|Annex)\s+([IVXLC0-9A-Z]+)\s*$", re.IGNORECASE)


def _clean_body(lines: list[str]) -> str:
    kept = [line.rstrip() for line in lines if not _PAGE_MARKER_RE.match(line)]
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept).strip()


def segment_numbered_list(text: str) -> tuple[list[SegmentedClause], list[str]]:
    """Segment a flat sequentially-numbered list such as
    'Secure PLC Coding Practices: Top 20 List' (1. Title / body, 2. Title / body, ...).

    A candidate heading is only accepted if its number is exactly the previous
    accepted number + 1, starting at 1. This rejects stray numbers that happen
    to appear inside body paragraphs.
    """
    lines = text.splitlines()
    clauses: list[SegmentedClause] = []
    diagnostics: list[str] = []
    expected_next = 1
    current: dict | None = None
    body_lines: list[str] = []

    def close_current(end_line: int) -> None:
        if current is None:
            return
        clauses.append(
            SegmentedClause(
                clause_number=current["number"],
                title=current["title"],
                text=_clean_body(body_lines),
                start_line=current["start_line"],
                end_line=end_line,
                parent_clause_number=None,
                provenance_class="EXTRACTED",
            )
        )

    for line_no, line in enumerate(lines, start=1):
        match = _NUMBERED_LIST_HEADING_RE.match(line)
        if match and int(match.group(1)) == expected_next and len(match.group(2)) < 120:
            close_current(line_no - 1)
            current = {"number": match.group(1), "title": match.group(2).strip(), "start_line": line_no}
            body_lines = []
            expected_next += 1
        else:
            body_lines.append(line)
    close_current(len(lines))

    if not clauses:
        diagnostics.append("numbered-list: no sequential heading found starting at 1")
    return clauses, diagnostics


def segment_en_iec_hierarchical(text: str) -> tuple[list[SegmentedClause], list[str]]:
    """Segment hierarchical EN/IEC-style clause numbering such as '4.2', '4.2.1',
    '4.2.1.1'. Table-of-contents lines are excluded by requiring the absence of
    a dot-leader run (e.g. '....... 13') on the heading line, since real body
    headings and TOC entries otherwise share the same numbering pattern.

    Also segments Annex headings ('Annex A', OCR'd 'AnnexZA' with no space) and their
    lettered sub-clauses ('A.1', 'ZA.2.3'). An Annex's own clause_number is the bare
    designator ('A', not 'Annex A') specifically so the existing rsplit-based parent
    resolution below correctly attaches 'A.1' to 'A' with no extra logic - the same
    mechanism that already attaches '4.2.1' to '4.2'.
    """
    lines = text.splitlines()
    clauses: list[SegmentedClause] = []
    diagnostics: list[str] = []
    current: dict | None = None
    body_lines: list[str] = []

    def close_current(end_line: int) -> None:
        if current is None:
            return
        number = current["number"]
        parent = number.rsplit(".", 1)[0] if "." in number else None
        clauses.append(
            SegmentedClause(
                clause_number=number,
                title=current["title"],
                text=_clean_body(body_lines),
                start_line=current["start_line"],
                end_line=end_line,
                parent_clause_number=parent,
                provenance_class="EXTRACTED",
            )
        )

    for line_no, line in enumerate(lines, start=1):
        if _DOT_LEADER_RE.search(line):
            continue  # table-of-contents entry, not a real heading
        match = _EN_IEC_HEADING_RE.match(line)
        annex_match = _EN_IEC_ANNEX_RE.match(line) if not match else None
        if match and len(match.group(2)) < 160:
            close_current(line_no - 1)
            current = {"number": match.group(1).upper(), "title": match.group(2).strip(), "start_line": line_no}
            body_lines = []
        elif annex_match:
            title = annex_match.group(2).strip() if annex_match.group(2) else ""
            close_current(line_no - 1)
            current = {"number": annex_match.group(1).upper(), "title": title, "start_line": line_no}
            body_lines = []
        else:
            body_lines.append(line)
    close_current(len(lines))

    if not clauses:
        diagnostics.append("en-iec-hierarchical: no non-TOC heading matched")
    return clauses, diagnostics


def segment_eu_regulation_article(text: str) -> tuple[list[SegmentedClause], list[str]]:
    """Segment EU-regulation-style 'Articolo N' headings, and 'Allegato N'/'Annex N'
    headings. Both must be the entire (trimmed) line, which distinguishes a real
    heading from inline references such as 'ai sensi dell'articolo 24' or
    'nell'allegato I' inside body text.

    Article/Annex titles are not separated from body text in this first pass (kept
    as a single text block) -- safe simplification, still gives correct boundaries
    and numbering. In particular this means a whole Annex (e.g. Machinery Regulation
    Annex I, which internally has "PARTE A"/"PARTE B" and numbered machinery
    categories) becomes ONE clause with all of that as raw text - sufficient for a
    human/LLM to read and decide what vocabulary it justifies (norm-product-
    classification skill, Workflow A), not attempting to auto-decompose it further.

    Annex clause numbers are prefixed 'Annex ' (e.g. 'Annex I') to keep them
    unambiguous alongside plain article numbers ('24') in the same document.
    """
    lines = text.splitlines()
    clauses: list[SegmentedClause] = []
    diagnostics: list[str] = []
    current: dict | None = None
    body_lines: list[str] = []

    def close_current(end_line: int) -> None:
        if current is None:
            return
        clauses.append(
            SegmentedClause(
                clause_number=current["number"],
                title="",
                text=_clean_body(body_lines),
                start_line=current["start_line"],
                end_line=end_line,
                parent_clause_number=None,
                provenance_class="EXTRACTED",
            )
        )

    for line_no, line in enumerate(lines, start=1):
        match = _ARTICLE_HEADING_RE.match(line)
        annex_match = _ANNEX_HEADING_RE.match(line) if not match else None
        if match:
            close_current(line_no - 1)
            current = {"number": match.group(1), "start_line": line_no}
            body_lines = []
        elif annex_match:
            close_current(line_no - 1)
            current = {"number": f"Annex {annex_match.group(1).upper()}", "start_line": line_no}
            body_lines = []
        else:
            body_lines.append(line)
    close_current(len(lines))

    if not clauses:
        diagnostics.append("eu-regulation-article: no 'Articolo N'/'Allegato N' heading matched")
    return clauses, diagnostics


_DRAFT_LINE_NUMBER_RE = re.compile(r"^\s*\d+\s+(.*)$")


def segment_line_numbered_draft(text: str) -> tuple[list[SegmentedClause], list[str]]:
    """Segment BSI 'Draft for Public Comment' (DPC) style documents. Real format
    confirmed via pdftotext on BS EN 50742-2025: every physical line is prefixed
    with an independent, sequential review line-number that has nothing to do with
    the document's own clause numbering, e.g. '267   7.2.1    General' - '267' is
    the DPC line counter (increments every line, including body text and blank-line
    gaps), '7.2.1' is the real clause number, 'General' is the title.

    Strips exactly one leading number+whitespace token from every line (the DPC
    counter only ever occupies that first position) and delegates the result to
    the existing en-iec-hierarchical logic, since the underlying clause numbering
    convention ('4.3', '7.2.1', 'Annex A') is identical once that prefix is gone -
    including its own TOC dot-leader exclusion, which still works correctly on the
    stripped text since dot-leaders survive the strip unchanged.
    """
    stripped_lines = []
    for line in text.splitlines():
        match = _DRAFT_LINE_NUMBER_RE.match(line)
        stripped_lines.append(match.group(1) if match else line)
    return segment_en_iec_hierarchical("\n".join(stripped_lines))


SEGMENTERS = {
    "numbered-list": segment_numbered_list,
    "en-iec-hierarchical": segment_en_iec_hierarchical,
    "eu-regulation-article": segment_eu_regulation_article,
    "line-numbered-draft": segment_line_numbered_draft,
}


def segment_by_family(text: str, document_family: str) -> tuple[list[SegmentedClause], list[str]]:
    segmenter = SEGMENTERS.get(document_family)
    if segmenter is None:
        return [], [f"unknown documentFamily '{document_family}', no segmenter available"]
    return segmenter(text)
