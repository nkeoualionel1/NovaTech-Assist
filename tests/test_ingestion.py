from pathlib import Path

from novatech.config import get_settings
from novatech.ingestion.documents import charger_documents, decouper_document
from novatech.ingestion.produits import charger_produits, texte_produit

DATA = get_settings().data_dir


def _ecrire(tmp_path: Path, corps: str) -> Path:
    path = tmp_path / "test_doc.md"
    entete = "---\nid: test_doc\ntitre: Document de test\ntype: guide\nmise_a_jour: 2026-10-01\n---\n"
    path.write_text(entete + corps, encoding="utf-8")
    return path


def test_une_section_par_passage_avec_chemin_de_titres(tmp_path):
    corps = (
        "# Document de test\n\nIntroduction.\n\n"
        "## Paiement\n\n### Moyens acceptés\nCarte bancaire.\n\n"
        "### Paiement en 3x\nDe 150 à 3 000 €.\n\n## Factures\nDans l'espace client.\n"
    )
    chunks = decouper_document(_ecrire(tmp_path, corps))
    assert [(c.section, c.contenu) for c in chunks] == [
        (None, "Introduction."),
        ("Paiement > Moyens acceptés", "Carte bancaire."),
        ("Paiement > Paiement en 3x", "De 150 à 3 000 €."),
        ("Factures", "Dans l'espace client."),
    ]
    assert chunks[1].id == "test_doc#01"
    assert chunks[1].texte_a_vectoriser().startswith("Document de test — Paiement > Moyens acceptés")


def test_section_longue_redecoupee_sans_couper_un_tableau(tmp_path):
    tableau = "| Mode | Tarif |\n|---|---|\n" + "\n".join(f"| mode {i} | {i} € |" for i in range(10))
    paragraphes = "\n\n".join(" ".join(["mot"] * 40) for _ in range(4))
    chunks = decouper_document(_ecrire(tmp_path, f"## Longue\n{paragraphes}\n\n{tableau}\n"), max_mots=100)
    assert len(chunks) > 1
    assert sum(tableau in c.contenu for c in chunks) == 1
    assert all(c.section == "Longue" for c in chunks)


def test_texte_produit_sans_stock_et_au_format_francais():
    produit = {
        "sku": "NT-X-1", "nom": "Test", "marque": "Nova", "categorie": "PC portable",
        "sous_categorie": "PC portable", "prix_ttc": 1599, "prix_barre": 1799.0, "stock": 0,
        "date_reapprovisionnement": "2026-12-04", "garantie_constructeur_ans": 2,
        "poids_kg": 1.3, "description": "Desc.", "caracteristiques": {"memoire": "16 Go"},
    }
    texte = texte_produit(produit)
    assert "1 599 € TTC (au lieu de 1 799 €)" in texte
    assert "Poids : 1,3 kg" in texte
    assert "- Mémoire : 16 Go" in texte
    assert "stock" not in texte.lower() and "2026-12-04" not in texte


def test_donnees_reelles():
    docs = charger_documents(DATA / "documents")
    produits = charger_produits(DATA / "catalogue" / "produits.json")
    assert len({c.source_id for c in docs}) == 23
    assert len(produits) == 100
    tous = docs + produits
    assert len({c.id for c in tous}) == len(tous)
    assert all(c.contenu.strip() for c in tous)
    # Chaque question de la FAQ doit devenir son propre passage.
    assert sum(c.source_id == "faq" for c in docs) >= 36
