from pathlib import Path

from novatech.config import get_settings
from novatech.ingestion.documents import chunk_document, load_documents
from novatech.ingestion.products import load_products, product_text

DATA_DIR = get_settings().data_dir


def _write_document(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "test_doc.md"
    front_matter = "---\nid: test_doc\ntitre: Document de test\ntype: guide\nmise_a_jour: 2026-10-01\n---\n"
    path.write_text(front_matter + body, encoding="utf-8")
    return path


def test_one_chunk_per_section_with_heading_path(tmp_path):
    body = (
        "# Document de test\n\nIntroduction.\n\n"
        "## Paiement\n\n### Moyens acceptés\nCarte bancaire.\n\n"
        "### Paiement en 3x\nDe 150 à 3 000 €.\n\n## Factures\nDans l'espace client.\n"
    )
    chunks = chunk_document(_write_document(tmp_path, body))
    assert [(c.section, c.content) for c in chunks] == [
        (None, "Introduction."),
        ("Paiement > Moyens acceptés", "Carte bancaire."),
        ("Paiement > Paiement en 3x", "De 150 à 3 000 €."),
        ("Factures", "Dans l'espace client."),
    ]
    assert chunks[1].id == "test_doc#01"
    assert chunks[1].text_to_embed().startswith("Document de test — Paiement > Moyens acceptés")


def test_long_section_split_without_breaking_a_table(tmp_path):
    table = "| Mode | Tarif |\n|---|---|\n" + "\n".join(f"| mode {i} | {i} € |" for i in range(10))
    paragraphs = "\n\n".join(" ".join(["mot"] * 40) for _ in range(4))
    chunks = chunk_document(_write_document(tmp_path, f"## Longue\n{paragraphs}\n\n{table}\n"),
                            max_words=100)
    assert len(chunks) > 1
    assert sum(table in c.content for c in chunks) == 1
    assert all(c.section == "Longue" for c in chunks)


def test_product_text_has_no_stock_and_french_number_format():
    product = {
        "sku": "NT-X-1", "nom": "Test", "marque": "Nova", "categorie": "PC portable",
        "sous_categorie": "PC portable", "prix_ttc": 1599, "prix_barre": 1799.0, "stock": 0,
        "date_reapprovisionnement": "2026-12-04", "garantie_constructeur_ans": 2,
        "poids_kg": 1.3, "description": "Desc.", "caracteristiques": {"memoire": "16 Go"},
    }
    text = product_text(product)
    assert "1 599 € TTC (au lieu de 1 799 €)" in text
    assert "Poids : 1,3 kg" in text
    assert "- Mémoire : 16 Go" in text
    assert "stock" not in text.lower() and "2026-12-04" not in text


def test_real_dataset():
    docs = load_documents(DATA_DIR / "documents")
    products = load_products(DATA_DIR / "catalogue" / "produits.json")
    assert len({c.source_id for c in docs}) == 23
    assert len(products) == 100
    assert products[0].id.startswith("product:") and products[0].metadata["category"]
    all_chunks = docs + products
    assert len({c.id for c in all_chunks}) == len(all_chunks)
    assert all(c.content.strip() for c in all_chunks)
    # Chaque question de la FAQ doit devenir son propre passage.
    assert sum(c.source_id == "faq" for c in docs) >= 36
