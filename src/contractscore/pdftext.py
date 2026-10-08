from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def pdf_pages(path: str | Path) -> list[str]:
    return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]


def pdf_text(path: str | Path) -> str:
    return "\n".join(pdf_pages(path))
