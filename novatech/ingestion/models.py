from dataclasses import dataclass, field


@dataclass
class Chunk:
    """Un passage indexé, prêt à être vectorisé."""

    id: str  # identifiant stable, ex. "livraison#03" ou "produit:NT-LAP-001"
    source_id: str  # id du document (= nom du fichier) ou SKU du produit, cité comme source
    source_type: str  # "document" | "produit"
    doc_type: str  # politique, faq, guide_depannage… ou "produit"
    titre: str
    section: str | None
    contenu: str
    metadata: dict = field(default_factory=dict)

    def texte_a_vectoriser(self) -> str:
        """Le titre et la section sont ajoutés au contenu pour donner du contexte au passage."""
        entete = self.titre if not self.section else f"{self.titre} — {self.section}"
        return f"{entete}\n{self.contenu}"
