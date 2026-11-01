"""Outils que Claude peut appeler : définitions (schémas JSON) et implémentations.

Chaque outil renvoie un dictionnaire sérialisé en JSON dans le tool_result.
Les règles de sécurité sont appliquées ICI, dans le code, et non confiées au modèle :
par exemple, suivi_commande ne renvoie rien si l'e-mail ne correspond pas.
"""

import json
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from ..retrieval import Recherche

CATEGORIES = [
    "PC portable", "PC fixe", "Écran", "Processeur", "Carte mère", "Carte graphique",
    "Mémoire RAM", "Stockage", "Alimentation", "Boîtier", "Refroidissement",
    "Périphérique", "Réseau",
]
SEUIL_STOCK_LIMITE = 5
HORAIRES_CONSEILLERS = {  # jour de la semaine (0 = lundi) -> (ouverture, fermeture)
    0: (9, 19), 1: (9, 19), 2: (9, 19), 3: (9, 19), 4: (9, 19), 5: (10, 17),
}

DEFINITIONS = [
    {
        "name": "rechercher_informations",
        "description": (
            "Recherche dans la base documentaire de NovaTech (livraison, retours, garantie, SAV, "
            "paiement, CGV, FAQ, services, guides de dépannage et de compatibilité) et dans les "
            "fiches du catalogue produits. Appelez cet outil AVANT de répondre à toute question "
            "sur les politiques, les produits, les prix, les caractéristiques techniques, la "
            "compatibilité ou le dépannage : ne répondez jamais de mémoire. Vous pouvez l'appeler "
            "plusieurs fois avec des requêtes différentes. Utilisez perimetre='produits' pour un "
            "conseil d'achat ou une question sur un produit précis."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "requete": {
                    "type": "string",
                    "description": "La question ou les mots-clés à rechercher, en français.",
                },
                "perimetre": {
                    "type": "string",
                    "enum": ["tout", "documents", "produits"],
                    "description": "Où chercher. Par défaut : tout.",
                },
                "categorie": {
                    "type": "string",
                    "enum": CATEGORIES,
                    "description": "Restreint la recherche produits à une catégorie.",
                },
            },
            "required": ["requete"],
            "additionalProperties": False,
        },
    },
    {
        "name": "verifier_stock",
        "description": (
            "Donne la disponibilité EN TEMPS RÉEL d'un produit (en stock, stock limité, rupture "
            "et date de réapprovisionnement). Appelez-le dès que le client demande si un produit "
            "est disponible, en stock, ou quand il pourra l'avoir. Les fiches produits ne "
            "contiennent pas le stock : seul cet outil fait foi."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "produit": {
                    "type": "string",
                    "description": "Référence (ex. NT-CPU-003) ou nom du produit (ex. Ryzen 7 7800X3D).",
                },
            },
            "required": ["produit"],
            "additionalProperties": False,
        },
    },
    {
        "name": "suivi_commande",
        "description": (
            "Renvoie le statut détaillé d'une commande (préparation, expédition, suivi transporteur, "
            "livraison, retour, remboursement). Exige le numéro de commande (format CMD-XXXXX) ET "
            "l'adresse e-mail utilisée lors de l'achat, tous deux fournis par le client dans la "
            "conversation. S'il manque l'un des deux, demandez-le au client au lieu d'appeler l'outil."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_commande": {"type": "string", "description": "Format CMD-XXXXX."},
                "email": {"type": "string", "description": "E-mail donné par le client."},
            },
            "required": ["numero_commande", "email"],
            "additionalProperties": False,
        },
    },
    {
        "name": "transferer_conseiller",
        "description": (
            "Transmet la demande à un conseiller humain, qui recontactera le client. Appelez-le "
            "quand le client demande à parler à un humain, quand il faut agir sur une commande "
            "(annulation, remboursement, changement d'adresse, geste commercial, litige), quand le "
            "client est mécontent, ou quand vous ne trouvez pas la réponse après recherche."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "motif": {
                    "type": "string",
                    "enum": [
                        "demande_client", "action_sur_commande", "reclamation",
                        "reponse_introuvable", "autre",
                    ],
                },
                "resume": {
                    "type": "string",
                    "description": "Résumé de la demande pour le conseiller, en une ou deux phrases.",
                },
                "numero_commande": {"type": "string", "description": "Si une commande est concernée."},
            },
            "required": ["motif", "resume"],
            "additionalProperties": False,
        },
    },
]


class Outils:
    def __init__(self, recherche: Recherche, date_reference: datetime):
        self.recherche = recherche
        self.conn: psycopg.Connection = recherche.conn
        self.date_reference = date_reference

    def executer(self, nom: str, entree: dict) -> tuple[dict, bool]:
        """Exécute un outil. Renvoie (résultat, est_une_erreur)."""
        fonction = getattr(self, nom, None)
        if nom not in {d["name"] for d in DEFINITIONS} or fonction is None:
            return {"erreur": f"Outil inconnu : {nom}"}, True
        try:
            resultat = fonction(**entree)
        except Exception as exc:  # l'erreur est renvoyée au modèle, qui pourra s'adapter
            return {"erreur": f"{type(exc).__name__} : {exc}"}, True
        return resultat, "erreur" in resultat

    # --- Outils -------------------------------------------------------------------------

    def rechercher_informations(self, requete: str, perimetre: str = "tout",
                                categorie: str | None = None) -> dict:
        filtres = {}
        if perimetre == "documents":
            filtres["source_type"] = "document"
        elif perimetre == "produits":
            filtres["source_type"] = "produit"
        if categorie:
            filtres["categorie"] = categorie
        resultats = self.recherche.rechercher(requete, k=5, filtres=filtres or None)
        return {
            "passages": [
                {"source": r.source_id, "titre": r.titre, "section": r.section, "contenu": r.contenu}
                for r in resultats
            ]
        }

    def verifier_stock(self, produit: str) -> dict:
        terme = produit.strip()
        with self.conn.cursor(row_factory=dict_row) as cur:
            lignes = cur.execute("SELECT * FROM produits WHERE sku = %s", [terme.upper()]).fetchall()
            if not lignes:
                # Tous les mots doivent apparaître dans le nom (« 7800X3D » trouve « AMD Ryzen 7 7800X3D »).
                mots = [m for m in terme.split() if len(m) > 1]
                if mots:
                    conditions = " AND ".join(["nom ILIKE %s"] * len(mots))
                    lignes = cur.execute(
                        f"SELECT * FROM produits WHERE {conditions} ORDER BY nom LIMIT 6",
                        [f"%{m}%" for m in mots],
                    ).fetchall()
        if not lignes:
            return {"erreur": f"Aucun produit ne correspond à « {produit} ». Cherchez d'abord la "
                              "référence avec rechercher_informations (perimetre='produits')."}
        if len(lignes) > 5:
            return {"erreur": "Trop de produits correspondent : précisez le nom ou la référence.",
                    "exemples": [l["nom"] for l in lignes[:5]]}
        return {"date_consultation": self.date_reference.isoformat(timespec="minutes"),
                "produits": [self._disponibilite(l) for l in lignes]}

    @staticmethod
    def _disponibilite(ligne: dict) -> dict:
        stock = ligne["stock"]
        if stock == 0:
            etat = "rupture de stock"
        elif stock <= SEUIL_STOCK_LIMITE:
            etat = f"stock limité ({stock} restant{'s' if stock > 1 else ''})"
        else:
            etat = "en stock"
        reappro = ligne["date_reapprovisionnement"]
        return {
            "reference": ligne["sku"],
            "nom": ligne["nom"],
            "prix_ttc": float(ligne["prix_ttc"]),
            "disponibilite": etat,
            "date_reapprovisionnement_prevue": reappro.isoformat() if reappro and stock == 0 else None,
        }

    def suivi_commande(self, numero_commande: str, email: str) -> dict:
        ligne = self.conn.execute(
            "SELECT donnees FROM commandes WHERE numero = %s AND email_client = %s",
            [numero_commande.strip().upper(), email.strip().lower()],
        ).fetchone()
        if ligne is None:
            # Même message que la commande existe ou non : on ne révèle rien à un tiers.
            return {"erreur": "Aucune commande ne correspond à ce numéro et à cette adresse e-mail. "
                              "Ne donnez aucune information sur cette commande."}
        c = ligne[0]
        return {
            "date_consultation": self.date_reference.isoformat(timespec="minutes"),
            "numero": c["numero"],
            "date_commande": c["date_commande"],
            "statut": c["statut_libelle"],
            "articles": [f"{l['quantite']} × {l['nom']}" for l in c["lignes"]],
            "services": [s["libelle"] for s in c["services"]],
            "total_ttc": c["total_ttc"],
            "moyen_paiement": c["moyen_paiement"],
            "mode_livraison": c["mode_livraison_libelle"],
            "transporteur": c["transporteur"],
            "numero_suivi": c["numero_suivi"],
            "date_expedition": c["date_expedition"],
            "date_livraison_estimee": c["date_livraison_estimee"],
            "date_livraison": c["date_livraison"],
            "retour": c["retour"],
            "historique": c["historique"],
            # L'adresse, le téléphone et l'identifiant client ne sont volontairement pas renvoyés.
        }

    def transferer_conseiller(self, motif: str, resume: str,
                              numero_commande: str | None = None) -> dict:
        identifiant = self.conn.execute(
            "INSERT INTO demandes_conseiller (motif, resume, numero_commande) "
            "VALUES (%s, %s, %s) RETURNING id",
            [motif, resume, numero_commande],
        ).fetchone()[0]
        maintenant = self.date_reference
        plage = HORAIRES_CONSEILLERS.get(maintenant.weekday())
        ouvert = bool(plage) and plage[0] <= maintenant.hour < plage[1]
        return {
            "reference_demande": f"DEM-{identifiant:06d}",
            "conseillers_disponibles_maintenant": ouvert,
            "horaires": "du lundi au vendredi de 9h à 19h, le samedi de 10h à 17h "
                        "(fermé le dimanche et les jours fériés)",
            "contact": {"telephone": "04 00 00 00 00", "email": "support@novatech-informatique.example"},
            "message": "Un conseiller recontactera le client"
                       + (" dans les meilleurs délais." if ouvert else " dès la réouverture."),
        }


def en_json(resultat: dict) -> str:
    return json.dumps(resultat, ensure_ascii=False, default=str)
