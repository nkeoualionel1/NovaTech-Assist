"""Lecture et découpage des documents Markdown.

Chaque section (titre ## ou ###) devient un passage. Une section trop longue est
redécoupée par paragraphes, sans jamais couper un tableau ou une liste.
"""

import re
from pathlib import Path

from .models import Chunk

MAX_WORDS = 300  # au-delà, une section est redécoupée
FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def read_document(path: Path) -> tuple[dict, str]:
    """Renvoie (front-matter, corps) d'un fichier Markdown."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = FRONT_MATTER.match(text)
    if not match:
        raise ValueError(f"{path.name} : front-matter manquant")
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.split(" #")[0].strip()
    # Clés du front-matter des documents sources (en français dans le dataset).
    for required in ("id", "titre", "type"):
        if not meta.get(required):
            raise ValueError(f"{path.name} : champ '{required}' absent du front-matter")
    return meta, text[match.end():]


def _split_sections(body: str) -> list[tuple[list[str], str]]:
    """Découpe le corps en (chemin de titres, texte) en suivant la hiérarchie des titres."""
    sections, path, lines = [], [], []
    in_code_block = False

    def flush():
        text = "\n".join(lines).strip()
        if text:
            sections.append((list(path), text))
        lines.clear()

    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            in_code_block = not in_code_block
        match = None if in_code_block else HEADING.match(line)
        if not match:
            lines.append(line)
            continue
        flush()
        level = len(match.group(1))
        # Le titre H1 est le titre du document : il n'entre pas dans le chemin de section.
        if level == 1:
            path = []
            continue
        path = path[: level - 2] + [match.group(2)]
    flush()
    return sections


def _split_long_text(text: str, max_words: int) -> list[str]:
    """Regroupe les paragraphes (séparés par une ligne vide) en morceaux d'au plus max_words."""
    if len(text.split()) <= max_words:
        return [text]
    pieces, current = [], []
    for paragraph in re.split(r"\n\s*\n", text):
        if current and len(" ".join(current + [paragraph]).split()) > max_words:
            pieces.append("\n\n".join(current))
            current = []
        current.append(paragraph)
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def chunk_document(path: Path, max_words: int = MAX_WORDS) -> list[Chunk]:
    meta, body = read_document(path)
    chunks = []
    for heading_path, text in _split_sections(body):
        section = " > ".join(heading_path) or None
        for piece in _split_long_text(text, max_words):
            chunks.append(
                Chunk(
                    id=f"{meta['id']}#{len(chunks):02d}",
                    source_id=meta["id"],
                    source_type="document",
                    doc_type=meta["type"],
                    title=meta["titre"],
                    section=section,
                    content=piece,
                    metadata={"file": path.name, "updated_on": meta.get("mise_a_jour")},
                )
            )
    return chunks


def load_documents(directory: Path) -> list[Chunk]:
    chunks = []
    for path in sorted(directory.rglob("*.md")):
        chunks.extend(chunk_document(path))
    return chunks
