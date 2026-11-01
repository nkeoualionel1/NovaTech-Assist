"""Transformation des fiches produits en passages texte.

Le stock n'est volontairement PAS écrit dans le passage : il change en permanence
et sera lu en direct par l'outil verifier_stock().
"""

import json
from pathlib import Path

from .models import Chunk

# Libellés lisibles pour les clés JSON (les autres sont dérivées automatiquement).
LIBELLES = {
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


def _libelle(cle: str) -> str:
    return LIBELLES.get(cle) or cle.replace("_", " ").capitalize()


def _nombre(valeur) -> str:
    """Format français : 1.3 → « 1,3 », 1599 → « 1 599 »."""
    if isinstance(valeur, float) and valeur.is_integer():
        valeur = int(valeur)
    if isinstance(valeur, int):
        return f"{valeur:,}".replace(",", " ")
    return str(valeur).replace(".", ",")


def _valeur(valeur) -> str:
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, list):
        return ", ".join(map(str, valeur))
    if isinstance(valeur, (int, float)):
        return _nombre(valeur)
    return str(valeur)


def texte_produit(p: dict) -> str:
    lignes = [
        f"Produit : {p['nom']} (référence {p['sku']})",
        f"Marque : {p['marque']} · Catégorie : {p['categorie']}"
        + (f" · Type : {p['sous_categorie']}" if p["sous_categorie"] != p["categorie"] else ""),
    ]
    prix = f"Prix : {_nombre(p['prix_ttc'])} € TTC"
    if p.get("prix_barre"):
        prix += f" (au lieu de {_nombre(p['prix_barre'])} €)"
    lignes.append(prix)

    garantie = p.get("garantie_constructeur_ans")
    if garantie is not None:
        duree = garantie if isinstance(garantie, str) else f"{garantie} an{'s' if garantie > 1 else ''}"
        lignes.append(f"Garantie constructeur : {duree}")
    if p.get("poids_kg"):
        lignes.append(f"Poids : {_nombre(p['poids_kg'])} kg")

    lignes += ["", p["description"], "", "Caractéristiques :"]
    lignes += [f"- {_libelle(k)} : {_valeur(v)}" for k, v in p["caracteristiques"].items()]
    return "\n".join(lignes)


def charger_produits(fichier: Path) -> list[Chunk]:
    produits = json.loads(fichier.read_text(encoding="utf-8"))
    return [
        Chunk(
            id=f"produit:{p['sku']}",
            source_id=p["sku"],
            source_type="produit",
            doc_type="produit",
            titre=p["nom"],
            section=None,
            contenu=texte_produit(p),
            # Le champ "compatibilite" est structuré : on le garde en métadonnées pour
            # des vérifications exactes plus tard (socket, DDR4/DDR5, longueur GPU…).
            metadata={
                "sku": p["sku"],
                "marque": p["marque"],
                "categorie": p["categorie"],
                "sous_categorie": p["sous_categorie"],
                "prix_ttc": p["prix_ttc"],
                "compatibilite": p.get("compatibilite"),
            },
        )
        for p in produits
    ]
