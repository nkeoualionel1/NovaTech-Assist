# NovaTech Assist

Assistant service client IA (RAG) pour l'enseigne fictive NovaTech Informatique.
Présentation du projet et des données : [Dataset/README.md](Dataset/README.md).

## Structure

```
Novatech-RAG/
├── Dataset/               Données, jeu de test et scripts de génération
├── novatech/
│   ├── config.py          Configuration (variables d'environnement / .env)
│   ├── ingestion/         Phase 3 : lecture → découpage → vectorisation → pgvector
│   ├── retrieval/         Phase 4 : recherche hybride (vecteurs + plein texte, fusion RRF)
│   └── assistant/         Phase 5 : Claude + outils (recherche, stock, commande, conseiller)
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

## Recherche hybride (phase 4)

```bash
python -m novatech.retrieval "Est-ce que vous livrez en Suisse ?"
python -m novatech.retrieval "portable léger" --filtre source_type=produit --k 3
python -m novatech.retrieval.evaluer --details     # qualité sur le jeu de test
```

Deux recherches sont lancées en parallèle puis fusionnées par **Reciprocal Rank Fusion** (RRF) :

- **vectorielle** (pgvector, similarité cosinus) : trouve les passages proches par le sens ;
- **plein texte** (PostgreSQL, dictionnaire français) : trouve les mots exacts, comme les références produit.

Filtres disponibles : `source_type` (document / produit), `doc_type`, `categorie`, `source_id`.

Résultats sur les 61 questions du jeu de test dont la source est indexée :

| Mode | Succès@1 | Succès@5 | MRR |
|---|---|---|---|
| Vectoriel seul | 64 % | 95 % | 0,78 |
| Plein texte seul | 64 % | 93 % | 0,75 |
| **Hybride** | **79 %** | **95 %** | **0,86** |

*Succès@k : la bonne source est parmi les k premiers passages. MRR : moyenne de 1/rang de la première bonne source.*

## Assistant avec Claude (phase 5)

Ajoutez votre clé dans `.env` (`ANTHROPIC_API_KEY=...`), puis :

```bash
python -m novatech.ingestion --magasin-seulement    # charge les tables produits et commandes
python -m novatech.assistant --details              # conversation dans le terminal
python -m novatech.assistant "Livrez-vous en Suisse ?"
```

Claude (`claude-opus-5-5` par défaut) dispose de 4 outils et décide lui-même lesquels appeler :

| Outil | Rôle | Règle appliquée dans le code |
|---|---|---|
| `rechercher_informations` | Recherche hybride (phase 4), avec filtre documents / produits / catégorie | — |
| `verifier_stock` | Disponibilité en temps réel, date de réapprovisionnement | Le stock n'est jamais lu dans les fiches indexées |
| `suivi_commande` | Statut, transporteur, retour, remboursement | Exige numéro **et** e-mail ; même réponse si la commande n'existe pas ou si l'e-mail est faux ; adresse et téléphone jamais renvoyés |
| `transferer_conseiller` | Crée une demande (`DEM-…`) et indique si les conseillers sont joignables | — |

- **Boucle d'agent** écrite à la main ([agent.py](novatech/assistant/agent.py)) : 6 tours d'outils au maximum, historique jamais modifié (seulement complété).
- **Sources vérifiées** : la ligne « Sources : » de la réponse est comparée aux passages réellement consultés ; une source citée sans avoir été lue est signalée.
- **Coûts** : consigne et définitions d'outils identiques à chaque appel, donc mises en cache par l'API.
- **Refus** : en cas de refus par un filtre de sécurité, l'API rejoue la requête sur un modèle de secours (`fallbacks="default"`).
