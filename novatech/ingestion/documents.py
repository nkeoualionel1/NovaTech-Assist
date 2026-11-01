"""Lecture et découpage des documents Markdown.

Chaque section (titre ## ou ###) devient un passage. Une section trop longue est
redécoupée par paragraphes, sans jamais couper un tableau ou une liste.
"""

import re
from pathlib import Path

from .models import Chunk

MAX_MOTS = 300  # au-delà, une section est redécoupée
FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
TITRE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def lire_document(path: Path) -> tuple[dict, str]:
    """Renvoie (front-matter, corps) d'un fichier Markdown."""
    texte = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = FRONT_MATTER.match(texte)
    if not m:
        raise ValueError(f"{path.name} : front-matter manquant")
    meta = {}
    for ligne in m.group(1).splitlines():
        if ":" in ligne:
            cle, valeur = ligne.split(":", 1)
            meta[cle.strip()] = valeur.split(" #")[0].strip()
    for champ in ("id", "titre", "type"):
        if not meta.get(champ):
            raise ValueError(f"{path.name} : champ '{champ}' absent du front-matter")
    return meta, texte[m.end():]


def _sections(corps: str) -> list[tuple[list[str], str]]:
    """Découpe le corps en (chemin de titres, texte) en suivant la hiérarchie des titres."""
    sections, chemin, lignes = [], [], []
    dans_code = False

    def vider():
        texte = "\n".join(lignes).strip()
        if texte:
            sections.append((list(chemin), texte))
        lignes.clear()

    for ligne in corps.split("\n"):
        if ligne.lstrip().startswith("```"):
            dans_code = not dans_code
        m = None if dans_code else TITRE.match(ligne)
        if not m:
            lignes.append(ligne)
            continue
        vider()
        niveau = len(m.group(1))
        # Le titre H1 est le titre du document : il n'entre pas dans le chemin de section.
        if niveau == 1:
            chemin = []
            continue
        chemin = chemin[: niveau - 2] + [m.group(2)]
    vider()
    return sections


def _redecouper(texte: str, max_mots: int) -> list[str]:
    """Regroupe les paragraphes (séparés par une ligne vide) en morceaux d'au plus max_mots."""
    if len(texte.split()) <= max_mots:
        return [texte]
    morceaux, courant = [], []
    for para in re.split(r"\n\s*\n", texte):
        if courant and len(" ".join(courant + [para]).split()) > max_mots:
            morceaux.append("\n\n".join(courant))
            courant = []
        courant.append(para)
    if courant:
        morceaux.append("\n\n".join(courant))
    return morceaux


def decouper_document(path: Path, max_mots: int = MAX_MOTS) -> list[Chunk]:
    meta, corps = lire_document(path)
    chunks = []
    for chemin, texte in _sections(corps):
        section = " > ".join(chemin) or None
        for morceau in _redecouper(texte, max_mots):
            chunks.append(
                Chunk(
                    id=f"{meta['id']}#{len(chunks):02d}",
                    source_id=meta["id"],
                    source_type="document",
                    doc_type=meta["type"],
                    titre=meta["titre"],
                    section=section,
                    contenu=morceau,
                    metadata={"fichier": path.name, "mise_a_jour": meta.get("mise_a_jour")},
                )
            )
    return chunks


def charger_documents(dossier: Path) -> list[Chunk]:
    chunks = []
    for path in sorted(dossier.rglob("*.md")):
        chunks.extend(decouper_document(path))
    return chunks
