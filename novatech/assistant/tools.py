"""Outils que Claude peut appeler : définitions (schémas JSON) et implémentations.

Chaque outil renvoie un dictionnaire sérialisé en JSON dans le tool_result.
Les règles de sécurité sont appliquées ICI, dans le code, et non confiées au modèle :
par exemple, track_order ne renvoie rien si l'e-mail ne correspond pas.
"""

import json
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from ..retrieval import Retriever

# Catégories du catalogue (valeurs du jeu de données, en français).
CATEGORIES = [
    "PC portable", "PC fixe", "Écran", "Processeur", "Carte mère", "Carte graphique",
    "Mémoire RAM", "Stockage", "Alimentation", "Boîtier", "Refroidissement",
    "Périphérique", "Réseau",
]
LOW_STOCK_THRESHOLD = 5
AGENT_HOURS = {  # jour de la semaine (0 = lundi) -> (ouverture, fermeture)
    0: (9, 19), 1: (9, 19), 2: (9, 19), 3: (9, 19), 4: (9, 19), 5: (10, 17),
}
HANDOFF_REASONS = ["customer_request", "order_action", "complaint", "answer_not_found", "other"]

TOOL_DEFINITIONS = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Recherche dans la base documentaire de NovaTech (livraison, retours, garantie, SAV, "
            "paiement, CGV, FAQ, services, guides de dépannage et de compatibilité) et dans les "
            "fiches du catalogue produits. Appelez cet outil AVANT de répondre à toute question "
            "sur les politiques, les produits, les prix, les caractéristiques techniques, la "
            "compatibilité ou le dépannage : ne répondez jamais de mémoire. Vous pouvez l'appeler "
            "plusieurs fois avec des requêtes différentes. Utilisez scope='products' pour un "
            "conseil d'achat ou une question sur un produit précis."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La question ou les mots-clés à rechercher, en français.",
                },
                "scope": {
                    "type": "string",
                    "enum": ["all", "documents", "products"],
                    "description": "Où chercher. Par défaut : all.",
                },
                "category": {
                    "type": "string",
                    "enum": CATEGORIES,
                    "description": "Restreint la recherche produits à une catégorie.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_stock",
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
                "product": {
                    "type": "string",
                    "description": "Référence (ex. NT-CPU-003) ou nom du produit (ex. Ryzen 7 7800X3D).",
                },
            },
            "required": ["product"],
            "additionalProperties": False,
        },
    },
    {
        "name": "track_order",
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
                "order_number": {"type": "string", "description": "Format CMD-XXXXX."},
                "email": {"type": "string", "description": "E-mail donné par le client."},
            },
            "required": ["order_number", "email"],
            "additionalProperties": False,
        },
    },
    {
        "name": "transfer_to_agent",
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
                "reason": {"type": "string", "enum": HANDOFF_REASONS},
                "summary": {
                    "type": "string",
                    "description": "Résumé de la demande pour le conseiller, en une ou deux phrases.",
                },
                "order_number": {"type": "string", "description": "Si une commande est concernée."},
            },
            "required": ["reason", "summary"],
            "additionalProperties": False,
        },
    },
]
TOOL_NAMES = {d["name"] for d in TOOL_DEFINITIONS}


class Toolbox:
    def __init__(self, retriever: Retriever, reference_date: datetime):
        self.retriever = retriever
        self.conn: psycopg.Connection = retriever.conn
        self.reference_date = reference_date

    def execute(self, name: str, tool_input: dict) -> tuple[dict, bool]:
        """Exécute un outil. Renvoie (résultat, est_une_erreur)."""
        handler = getattr(self, name, None)
        if name not in TOOL_NAMES or handler is None:
            return {"error": f"Outil inconnu : {name}"}, True
        try:
            result = handler(**tool_input)
        except Exception as exc:  # l'erreur est renvoyée au modèle, qui pourra s'adapter
            return {"error": f"{type(exc).__name__} : {exc}"}, True
        return result, "error" in result

    # --- Outils -------------------------------------------------------------------------

    def search_knowledge_base(self, query: str, scope: str = "all",
                              category: str | None = None) -> dict:
        filters = {}
        if scope == "documents":
            filters["source_type"] = "document"
        elif scope == "products":
            filters["source_type"] = "product"
        if category:
            filters["category"] = category
        results = self.retriever.search(query, k=5, filters=filters or None)
        return {
            "passages": [
                {"source": r.source_id, "title": r.title, "section": r.section, "content": r.content}
                for r in results
            ]
        }

    def check_stock(self, product: str) -> dict:
        term = product.strip()
        with self.conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute("SELECT * FROM products WHERE sku = %s", [term.upper()]).fetchall()
            if not rows:
                # Tous les mots doivent apparaître dans le nom (« 7800X3D » trouve « AMD Ryzen 7 7800X3D »).
                words = [w for w in term.split() if len(w) > 1]
                if words:
                    conditions = " AND ".join(["name ILIKE %s"] * len(words))
                    rows = cur.execute(
                        f"SELECT * FROM products WHERE {conditions} ORDER BY name LIMIT 6",
                        [f"%{w}%" for w in words],
                    ).fetchall()
        if not rows:
            return {"error": f"Aucun produit ne correspond à « {product} ». Cherchez d'abord la "
                             "référence avec search_knowledge_base (scope='products')."}
        if len(rows) > 5:
            return {"error": "Trop de produits correspondent : précisez le nom ou la référence.",
                    "examples": [row["name"] for row in rows[:5]]}
        return {"checked_at": self.reference_date.isoformat(timespec="minutes"),
                "products": [self._availability(row) for row in rows]}

    @staticmethod
    def _availability(row: dict) -> dict:
        stock = row["stock"]
        if stock == 0:
            status = "rupture de stock"
        elif stock <= LOW_STOCK_THRESHOLD:
            status = f"stock limité ({stock} restant{'s' if stock > 1 else ''})"
        else:
            status = "en stock"
        restock = row["restock_date"]
        return {
            "reference": row["sku"],
            "name": row["name"],
            "price_incl_vat": float(row["price_incl_vat"]),
            "availability": status,
            "expected_restock_date": restock.isoformat() if restock and stock == 0 else None,
        }

    def track_order(self, order_number: str, email: str) -> dict:
        row = self.conn.execute(
            "SELECT data FROM orders WHERE order_number = %s AND customer_email = %s",
            [order_number.strip().upper(), email.strip().lower()],
        ).fetchone()
        if row is None:
            # Même message que la commande existe ou non : on ne révèle rien à un tiers.
            return {"error": "Aucune commande ne correspond à ce numéro et à cette adresse e-mail. "
                             "Ne donnez aucune information sur cette commande."}
        order = row[0]  # clés du jeu de données source
        return {
            "checked_at": self.reference_date.isoformat(timespec="minutes"),
            "order_number": order["numero"],
            "order_date": order["date_commande"],
            "status": order["statut_libelle"],
            "items": [f"{line['quantite']} × {line['nom']}" for line in order["lignes"]],
            "services": [s["libelle"] for s in order["services"]],
            "total_incl_vat": order["total_ttc"],
            "payment_method": order["moyen_paiement"],
            "delivery_method": order["mode_livraison_libelle"],
            "carrier": order["transporteur"],
            "tracking_number": order["numero_suivi"],
            "shipped_on": order["date_expedition"],
            "estimated_delivery_date": order["date_livraison_estimee"],
            "delivered_on": order["date_livraison"],
            "return": order["retour"],
            "history": order["historique"],
            # L'adresse, le téléphone et l'identifiant client ne sont volontairement pas renvoyés.
        }

    def transfer_to_agent(self, reason: str, summary: str, order_number: str | None = None) -> dict:
        request_id = self.conn.execute(
            "INSERT INTO handoff_requests (reason, summary, order_number) "
            "VALUES (%s, %s, %s) RETURNING id",
            [reason, summary, order_number],
        ).fetchone()[0]
        now = self.reference_date
        opening_hours = AGENT_HOURS.get(now.weekday())
        is_open = bool(opening_hours) and opening_hours[0] <= now.hour < opening_hours[1]
        return {
            "request_reference": f"DEM-{request_id:06d}",
            "agents_available_now": is_open,
            "hours": "du lundi au vendredi de 9h à 19h, le samedi de 10h à 17h "
                     "(fermé le dimanche et les jours fériés)",
            "contact": {"phone": "04 00 00 00 00", "email": "support@novatech-informatique.example"},
            "message": "Un conseiller recontactera le client"
                       + (" dans les meilleurs délais." if is_open else " dès la réouverture."),
        }


def to_json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)
