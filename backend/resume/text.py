"""Plain text of a resume file: PDF or Word (.docx)."""
from __future__ import annotations

from pathlib import Path

SUPPORTED = (".pdf", ".docx")


def resume_text(path: str | Path) -> str:
    """Text of a .pdf or .docx resume. Raises ValueError for other formats."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        import pymupdf
        with pymupdf.open(str(p)) as doc:
            return "\n".join(page.get_text() for page in doc).strip()
    if suffix == ".docx":
        import docx
        d = docx.Document(str(p))
        parts = [para.text for para in d.paragraphs]
        for table in d.tables:  # many resume templates lay sections out in tables
            for row in table.rows:
                cells = []
                for cell in row.cells:
                    if cell.text.strip() and cell.text not in cells:  # merged cells repeat
                        cells.append(cell.text.strip())
                parts.append(" | ".join(cells))
        header: list[str] = []
        for section in d.sections:  # name and contact details often sit in the header
            try:
                if not section.header.is_linked_to_previous:
                    header += [para.text for para in section.header.paragraphs]
            except Exception:
                pass
        parts = header + parts
        return "\n".join(x for x in (s.strip() for s in parts) if x).strip()
    raise ValueError(f"Unsupported resume format {suffix or '(none)'}: use PDF or Word (.docx).")
