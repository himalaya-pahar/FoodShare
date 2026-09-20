"""Load knowledge-base markdown documents from ai/knowledge_base/."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# Located at project_root/ai/knowledge_base/. Resolved relative to this file so
# the loader works regardless of CWD.
KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"


@dataclass(frozen=True)
class Document:
    name: str            # e.g. "business-rules.md"
    path: Path
    content: str


def load_all_documents(kb_dir: Path | None = None) -> list[Document]:
    """Load every *.md file under the knowledge_base/ directory.

    Skips files whose name starts with '_' (reserved for future helpers).
    Raises FileNotFoundError if the directory is missing.
    """
    root = kb_dir or KB_DIR
    if not root.exists():
        raise FileNotFoundError(
            f"Knowledge base directory not found: {root}. "
            "Did you delete ai/knowledge_base/?"
        )

    docs: list[Document] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() != ".md":
            continue
        if entry.name.startswith("_"):
            continue
        text = entry.read_text(encoding="utf-8")
        docs.append(Document(name=entry.name, path=entry, content=text))
    return docs


def list_document_names(kb_dir: Path | None = None) -> list[str]:
    """Cheap list of doc filenames without reading them."""
    root = kb_dir or KB_DIR
    if not root.exists():
        return []
    return sorted(
        e.name
        for e in root.iterdir()
        if e.is_file() and e.suffix.lower() == ".md" and not e.name.startswith("_")
    )


def assert_no_env_keys_present(text: str, filename: str) -> None:
    """Defensive: fail loudly if a KB file accidentally contains a credential."""
    if "sk-" in text or "sb_secret_" in text:
        raise RuntimeError(
            f"{filename}: looks like an API key is embedded in the KB. "
            "Refusing to index."
        )