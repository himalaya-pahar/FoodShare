"""Section-aware Markdown chunker.

For v1 the strategy is:
    1. Split on `## ` and `### ` headings (preserves section names as metadata).
    2. If a section exceeds CHUNK_SIZE characters, fall back to a recursive
       character splitter on paragraph / line boundaries with a small overlap.

This is intentionally simple — see CONTEXT.md "non-goals for v1" for why we
are not pulling in langchain-style chunking yet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config import CHUNK_OVERLAP, CHUNK_SIZE


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", flags=re.MULTILINE)
_DOC_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")


@dataclass(frozen=True)
class Chunk:
    document: str       # e.g. "business-rules.md"
    section: str        # e.g. "Donation state machine"
    chunk_id: str       # unique within the doc, e.g. "business-rules-03"
    text: str           # the chunk content (no markdown heading at the start)
    order: int          # 0-based order within the document


def _stable_chunk_id(doc_name: str, order: int) -> str:
    base = doc_name.rsplit(".", 1)[0]
    return f"{base}-{order:03d}"


def _split_section(
    section_name: str,
    body: str,
    max_size: int,
    overlap: int,
) -> list[str]:
    """Recursive character splitter (paragraph → line → sentence → char).

    Keeps characters simple — we are not doing multilingual tokenization here.
    """
    text = body.strip()
    if not text:
        return []
    if len(text) <= max_size:
        return [text]

    # Try paragraph breaks first.
    for sep in ("\n\n", "\n", ". ", " "):
        parts = text.split(sep)
        if all(len(p) <= max_size for p in parts if p):
            chunks = _join_with_overlap(parts, sep, max_size, overlap)
            if chunks:
                return chunks

    # Last resort: hard split.
    chunks: list[str] = []
    step = max_size - overlap
    for start in range(0, len(text), step):
        chunks.append(text[start : start + max_size])
    return chunks


def _join_with_overlap(
    parts: list[str], sep: str, max_size: int, overlap: int
) -> list[str]:
    """Re-join split parts into chunks of <= max_size with `overlap` shared chars."""
    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = (current + sep + part).strip() if current else part
        if len(candidate) > max_size and current:
            chunks.append(current)
            tail = current[-overlap:] if overlap > 0 else ""
            current = (tail + sep + part).strip()
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def chunk_document(
    doc_name: str,
    content: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Split one document into Chunk objects.

    Heading hierarchy is collapsed to a single 'section' string for metadata —
    v1 does not preserve sub-section nesting. Good enough for retrieval.
    """
    chunk_size = chunk_size or CHUNK_SIZE
    chunk_overlap = chunk_overlap or CHUNK_OVERLAP

    # Identify all heading positions.
    headings = list(_HEADING_RE.finditer(content))
    if not headings:
        # Document with no headings → treat the whole thing as one section.
        section_name = doc_name.rsplit(".", 1)[0]
        pieces = _split_section(section_name, content, chunk_size, chunk_overlap)
        return [
            Chunk(
                document=doc_name,
                section=section_name,
                chunk_id=_stable_chunk_id(doc_name, i),
                text=p,
                order=i,
            )
            for i, p in enumerate(pieces)
        ]

    chunks: list[Chunk] = []
    order = 0
    # First pass: pair each heading with its body.
    for idx, match in enumerate(headings):
        section_name = match.group(2).strip()
        body_start = match.end()
        body_end = headings[idx + 1].start() if idx + 1 < len(headings) else len(content)
        body = content[body_start:body_end]
        body = _strip_doc_title(body)

        pieces = _split_section(section_name, body, chunk_size, chunk_overlap)
        for piece in pieces:
            if not piece.strip():
                continue
            chunks.append(
                Chunk(
                    document=doc_name,
                    section=section_name,
                    chunk_id=_stable_chunk_id(doc_name, order),
                    text=piece.strip(),
                    order=order,
                )
            )
            order += 1

    return chunks


def _strip_doc_title(text: str) -> str:
    """Drop leading '# Title' line if present (it was already captured)."""
    match = _DOC_TITLE_RE.match(text.lstrip("\n"))
    if not match:
        return text
    return text[match.end():]
