from dataclasses import dataclass, field


@dataclass
class Chunk:
    """Un passage indexé, prêt à être vectorisé."""

    id: str  # identifiant stable, ex. "livraison#03" ou "product:NT-LAP-001"
    source_id: str  # id du document (= nom du fichier) ou SKU du produit, cité comme source
    source_type: str  # "document" | "product"
    doc_type: str  # politique, faq, guide_depannage… ou "product"
    title: str
    section: str | None
    content: str
    metadata: dict = field(default_factory=dict)

    def text_to_embed(self) -> str:
        """Le titre et la section sont ajoutés au contenu pour donner du contexte au passage."""
        heading = self.title if not self.section else f"{self.title} — {self.section}"
        return f"{heading}\n{self.content}"
