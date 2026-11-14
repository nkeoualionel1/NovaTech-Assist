"""Chargement des tables « métier » lues par les outils de l'assistant.

Contrairement aux documents, ces données ne sont PAS vectorisées :
- products : stock et date de réapprovisionnement, lus par check_stock() ;
- orders : données personnelles, lues uniquement par track_order() après
  vérification du couple numéro de commande + e-mail.
"""

import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

SCHEMA = """
DROP TABLE IF EXISTS products, orders;

CREATE TABLE products (
    sku            TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    category       TEXT NOT NULL,
    price_incl_vat NUMERIC(10, 2) NOT NULL,
    stock          INTEGER NOT NULL,
    restock_date   DATE
);

-- data : la commande telle qu'elle figure dans le jeu de données source.
CREATE TABLE orders (
    order_number   TEXT PRIMARY KEY,
    customer_email TEXT NOT NULL,
    status         TEXT NOT NULL,
    data           JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS handoff_requests (
    id           SERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason       TEXT NOT NULL,
    summary      TEXT NOT NULL,
    order_number TEXT
);
"""


def load_shop_tables(database_url: str, data_dir: Path) -> tuple[int, int]:
    products = json.loads((data_dir / "catalogue" / "produits.json").read_text(encoding="utf-8"))
    orders = json.loads((data_dir / "commandes" / "commandes.json").read_text(encoding="utf-8"))

    with psycopg.connect(database_url) as conn, conn.transaction():
        conn.execute(SCHEMA)
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO products VALUES (%s, %s, %s, %s, %s, %s)",
                [(p["sku"], p["nom"], p["categorie"], p["prix_ttc"], p["stock"],
                  p["date_reapprovisionnement"]) for p in products],
            )
            cur.executemany(
                "INSERT INTO orders VALUES (%s, %s, %s, %s)",
                [(o["numero"], o["email_client"].lower(), o["statut"], Jsonb(o)) for o in orders],
            )
    return len(products), len(orders)
