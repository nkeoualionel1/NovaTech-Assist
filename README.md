# NovaTech Assist

Assistant service client IA (RAG) pour l'enseigne fictive NovaTech Informatique.
Présentation du projet et des données : [Dataset/README.md](Dataset/README.md).

## Structure

```
Novatech-RAG/
├── Dataset/               Données, jeu de test et scripts de génération
├── novatech/
│   ├── config.py          Configuration (variables d'environnement / .env)
│   └── ingestion/         Phase 3 : lecture → découpage → vectorisation → pgvector
├── tests/
└── docker-compose.yml     PostgreSQL 17 + pgvector
```

## Installation

Prérequis : Python 3.10+ et [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # Linux/macOS : cp .env.example .env
docker compose up -d              # démarre la base
```

## Ingestion (phase 3)

```bash
python -m novatech.ingestion --dry-run   # découpage seul, sans modèle ni base
python -m novatech.ingestion             # index complet dans PostgreSQL
pytest
```

| Source | Découpage | Résultat |
|---|---|---|
| `documents/*.md` | une section `##` / `###` = un passage (redécoupé au-delà de 300 mots, sans couper les tableaux) | 164 passages |
| `catalogue/produits.json` | une fiche = un passage, **sans le stock** (lu en direct par l'outil `verifier_stock`) | 100 passages |

- **Modèle d'embedding** : `intfloat/multilingual-e5-base` (local, 768 dimensions, téléchargé au premier lancement).
- **Base** : table `chunks` avec un index vectoriel HNSW (recherche par sens) et un index plein texte en français (recherche par mots-clés), prêts pour la recherche hybride de la phase 4.
- L'ingestion **reconstruit tout l'index dans une seule transaction** : on peut la relancer après chaque modification des documents ; en cas d'erreur, l'ancien index reste en place.
- Les clients et commandes ne sont **jamais indexés** (données personnelles).
