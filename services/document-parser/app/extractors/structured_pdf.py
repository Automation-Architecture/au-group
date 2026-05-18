import logging
from dataclasses import dataclass, field
from pathlib import Path

import fitz
import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class PageText:
    page: int
    lines: list[str] = field(default_factory=list)


@dataclass
class StructuredPdfResult:
    text: str
    page_count: int
    pages: list[PageText] = field(default_factory=list)
    tables: list[list[list[str | None]]] = field(default_factory=list)


def extract_structured_pdf(path: Path) -> StructuredPdfResult:
    pages: list[PageText] = []
    tables: list[list[list[str | None]]] = []
    all_lines: list[str] = []

    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        for index, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            pages.append(PageText(page=index, lines=lines))
            all_lines.extend(lines)
            for table in page.extract_tables() or []:
                tables.append(table)

    if not all_lines:
        with fitz.open(path) as doc:
            for index in range(doc.page_count):
                page_text = doc.load_page(index).get_text("text") or ""
                lines = [line.strip() for line in page_text.splitlines() if line.strip()]
                if index < len(pages):
                    pages[index].lines = lines
                else:
                    pages.append(PageText(page=index + 1, lines=lines))
                all_lines.extend(lines)
            page_count = doc.page_count

    return StructuredPdfResult(
        text="\n".join(all_lines),
        page_count=page_count if pages else 0,
        pages=pages,
        tables=tables,
    )


def probe_text_density(path: Path, min_chars: int) -> tuple[int, float]:
    """Return page_count and fraction of pages with at least min_chars of embedded text."""
    with fitz.open(path) as doc:
        page_count = doc.page_count
        if page_count == 0:
            return 0, 0.0
        rich_pages = 0
        for index in range(page_count):
            text = doc.load_page(index).get_text("text") or ""
            if len(text.strip()) >= min_chars:
                rich_pages += 1
        return page_count, rich_pages / page_count
