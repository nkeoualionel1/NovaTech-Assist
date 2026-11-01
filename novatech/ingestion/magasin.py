"""Chargement des tables « métier » lues par les outils de l'assistant.

Contrairement aux documents, ces données ne sont PAS vectorisées :
- produits : stock et date de réapprovisionnement, lus par verifier_stock() ;
- commandes : données personnelles, lues uniquement par suivi_commande() après
  vérification du couple numéro de commande + e-mail.
"""

import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

SCHEMA = """
DROP TABLE IF EXISTS produits, commandes;

CREATE TABLE produits (
    sku                      TEXT PRIMARY KEY,
    nom                      TEXT NOT NULL,
    categorie                TEXT NOT NULL,
    prix_ttc                 NUMERIC(10, 2) NOT NULL,
    stock                    INTEGER NOT NULL,
    date_reapprovisionnement DATE
);

CREATE TABLE commandes (
    numero       TEXT PRIMARY KEY,
    email_client TEXT NOT NULL,
    statut       TEXT NOT NULL,
    donnees      JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS demandes_conseiller (
    id              SERIAL PRIMARY KEY,
    cree_le         TIMESTAMPTZ NOT NULL DEFAULT now(),
    motif           TEXT NOT NULL,
    resume          TEXT NOT NULL,
    numero_commande TEXT
);
"""


def charger_tables_magasin(database_url: str, data_dir: Path) -> tuple[int, int]:
    produits = json.loads((data_dir / "catalogue" / "produits.json").read_text(encoding="utf-8"))
    commandes = json.loads((data_dir / "commandes" / "commandes.json").read_text(encoding="utf-8"))

    with psycopg.connect(database_url) as conn, conn.transaction():
        conn.execute(SCHEMA)
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO produits VALUES (%s, %s, %s, %s, %s, %s)",
                [(p["sku"], p["nom"], p["categorie"], p["prix_ttc"], p["stock"],
                  p["date_reapprovisionnement"]) for p in produits],
            )
            cur.executemany(
                "INSERT INTO commandes VALUES (%s, %s, %s, %s)",
                [(c["numero"], c["email_client"].lower(), c["statut"], Jsonb(c)) for c in commandes],
            )
    return len(produits), len(commandes)
