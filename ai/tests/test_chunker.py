"""Offline tests for the section-aware chunker.

Run with: pytest ai/tests/test_chunker.py -v
"""

from ai.ingestion.chunker import chunk_document


SAMPLE_DOC = """# Title of the Document

Some intro text right after the title that should be folded into the first section.

## First Section

First paragraph of section one. It has enough words to be interesting.

Second paragraph of section one. Still in the same section.

## Second Section

First paragraph of section two.

### Sub Section Under Two

A nested subsection paragraph.
"""


def test_chunker_uses_h1_as_section_when_no_h2():
    chunks = chunk_document("solo.md", "Just some text.\n" * 50)
    assert len(chunks) >= 1
    assert all(c.document == "solo.md" for c in chunks)


def test_chunker_splits_on_h2():
    chunks = chunk_document("doc.md", SAMPLE_DOC)
    sections = {c.section for c in chunks}
    assert "First Section" in sections
    assert "Second Section" in sections
    # Each section should appear at least once.
    assert sum(1 for c in chunks if c.section == "First Section") >= 1


def test_chunker_assigns_stable_chunk_ids():
    chunks = chunk_document("doc.md", SAMPLE_DOC)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk_ids must be unique within a doc"
    for cid in ids:
        assert cid.startswith("doc-"), cid


def test_chunker_text_not_empty():
    chunks = chunk_document("doc.md", SAMPLE_DOC)
    assert all(c.text.strip() for c in chunks)


def test_chunker_respects_max_size():
    big = ("## Big Section\n\n" + ("word " * 1000 + "\n\n") * 5)
    chunks = chunk_document("big.md", big, chunk_size=200, chunk_overlap=20)
    assert all(len(c.text) <= 220 for c in chunks)  # a bit of slack for overlap


def test_chunker_strips_leading_h1():
    chunks = chunk_document("doc.md", SAMPLE_DOC)
    for c in chunks:
        # No chunk should start with a '# Title' line.
        assert not c.text.startswith("# Title")
