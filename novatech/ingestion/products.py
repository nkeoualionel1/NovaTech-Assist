"""Transformation des fiches produits en passages texte.

Le stock n'est volontairement PAS écrit dans le passage : il change en permanence
et sera lu en direct par l'outil check_stock().
"""

import json
from pathlib import Path

from .models import Chunk

# Libellés lisibles pour les clés JSON du catalogue (les autres sont dérivés automatiquement).
LABELS = {
    "memoire": "Mémoire",
    "ecran": "Écran",
    "carte_graphique": "Carte graphique",
    "carte_mere": "Carte mère",
    "systeme": "Système",
    "boitier": "Boîtier",
    "connectique_facade": "Connectique en façade",
    "coeurs_threads": "Cœurs / threads",
    "frequence": "Fréquence",
    "graphique_integre": "Graphique intégré",
    "memoire_supportee": "Mémoire supportée",
    "resolution": "Résolution",
    "reseau": "Réseau",
    "usb_arriere": "USB à l'arrière",
    "sortie_video": "Sortie vidéo",
    "latence": "Latence",
    "capacite": "Capacité",
    "ecriture": "Écriture",
    "compatibilite_ps5": "Compatible PS5",
    "modularite": "Modularité",
    "temps_reponse": "Temps de réponse",
    "debit": "Débit",
    "retroeclairage": "Rétroéclairage",
    "alimentation_conseillee": "Alimentation conseillée",
    "connecteur_alim": "Connecteur d'alimentation",
    "format_carte_mere": "Format de carte mère",
    "gpu_longueur_max": "Longueur max. de carte graphique",
    "ventirad_hauteur_max": "Hauteur max. du ventirad",
    "ventilateurs_inclus": "Ventilateurs inclus",
    "ventirad_inclus": "Ventirad inclus",
    "tdp_max": "TDP max.",
    "haut_parleurs": "Haut-parleurs",
    "connecteurs_pcie": "Connecteurs PCIe",
    "garantie_marquage": "Garantie marquage (burn-in)",
    "gpu": "GPU",
    "hdr": "HDR",
    "npu": "NPU",
    "os": "Système",
    "pcie": "PCIe",
    "prerequis": "Prérequis",
    "reduction_bruit": "Réduction de bruit",
    "refroidissement_conseille": "Refroidissement conseillé",
    "resistance": "Résistance",
    "securite": "Sécurité",
    "tdp": "TDP",
    "usb": "USB",
    "vesa": "VESA",
}


def _label(key: str) -> str:
    return LABELS.get(key) or key.replace("_", " ").capitalize()


def _format_number(value) -> str:
    """Format français : 1.3 → « 1,3 », 1599 → « 1 599 »."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    return str(value).replace(".", ",")


def _format_value(value) -> str:
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, list):
        return ", ".join(map(str, value))
    if isinstance(value, (int, float)):
        return _format_number(value)
    return str(value)


def product_text(p: dict) -> str:
    """Fiche lisible d'un produit (les clés du dict sont celles du catalogue source)."""
    lines = [
        f"Produit : {p['nom']} (référence {p['sku']})",
        f"Marque : {p['marque']} · Catégorie : {p['categorie']}"
        + (f" · Type : {p['sous_categorie']}" if p["sous_categorie"] != p["categorie"] else ""),
    ]
    price = f"Prix : {_format_number(p['prix_ttc'])} € TTC"
    if p.get("prix_barre"):
        price += f" (au lieu de {_format_number(p['prix_barre'])} €)"
    lines.append(price)

    warranty = p.get("garantie_constructeur_ans")
    if warranty is not None:
        duration = warranty if isinstance(warranty, str) else f"{warranty} an{'s' if warranty > 1 else ''}"
        lines.append(f"Garantie constructeur : {duration}")
    if p.get("poids_kg"):
        lines.append(f"Poids : {_format_number(p['poids_kg'])} kg")

    lines += ["", p["description"], "", "Caractéristiques :"]
    lines += [f"- {_label(k)} : {_format_value(v)}" for k, v in p["caracteristiques"].items()]
    return "\n".join(lines)


def load_products(catalog_file: Path) -> list[Chunk]:
    products = json.loads(catalog_file.read_text(encoding="utf-8"))
    return [
        Chunk(
            id=f"product:{p['sku']}",
            source_id=p["sku"],
            source_type="product",
            doc_type="product",
            title=p["nom"],
            section=None,
            content=product_text(p),
            # Le champ "compatibilite" est structuré : on le garde en métadonnées pour
            # des vérifications exactes plus tard (socket, DDR4/DDR5, longueur GPU…).
            metadata={
                "sku": p["sku"],
                "brand": p["marque"],
                "category": p["categorie"],
                "subcategory": p["sous_categorie"],
                "price_incl_vat": p["prix_ttc"],
                "compatibility": p.get("compatibilite"),
            },
        )
        for p in products
    ]
