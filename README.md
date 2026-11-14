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
│   ├── assistant/         Phase 5 : Claude + outils (recherche, stock, commande, conseiller)
│   ├── guardrails/        Phase 6 : filtres d'entrée et de sortie, limites, journal
│   ├── evaluation/        Phase 8 : runner et notation (contrôles automatiques + juge Claude)
│   └── api/               Phase 7 : API FastAPI (flux SSE) qui sert aussi l'interface
├── frontend/              Phase 7 : interface de chat React + TypeScript (Vite)
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
| `catalogue/produits.json` | une fiche = un passage, **sans le stock** (lu en direct par l'outil `check_stock`) | 100 passages |

- **Modèle d'embedding** : `intfloat/multilingual-e5-base` (local, 768 dimensions, téléchargé au premier lancement).
- **Base** : table `chunks` avec un index vectoriel HNSW (recherche par sens) et un index plein texte en français (recherche par mots-clés), prêts pour la recherche hybride de la phase 4.
- L'ingestion **reconstruit tout l'index dans une seule transaction** : on peut la relancer après chaque modification des documents ; en cas d'erreur, l'ancien index reste en place.
- Les clients et commandes ne sont **jamais indexés** (données personnelles).

## Recherche hybride (phase 4)

```bash
python -m novatech.retrieval "Est-ce que vous livrez en Suisse ?"
python -m novatech.retrieval "portable léger" --filter source_type=product --k 3
python -m novatech.retrieval.evaluate --details    # qualité sur le jeu de test
```

Deux recherches sont lancées en parallèle puis fusionnées par **Reciprocal Rank Fusion** (RRF) :

- **vectorielle** (pgvector, similarité cosinus) : trouve les passages proches par le sens ;
- **plein texte** (PostgreSQL, dictionnaire français) : trouve les mots exacts, comme les références produit.

Filtres disponibles : `source_type` (document / product), `doc_type`, `category`, `source_id`.

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
python -m novatech.ingestion --shop-only           # charge les tables products et orders
python -m novatech.assistant --details              # conversation dans le terminal
python -m novatech.assistant "Livrez-vous en Suisse ?"
```

Claude (`claude-opus-5-5` par défaut) dispose de 4 outils et décide lui-même lesquels appeler :

| Outil | Rôle | Règle appliquée dans le code |
|---|---|---|
| `search_knowledge_base` | Recherche hybride (phase 4), avec filtre documents / produits / catégorie | — |
| `check_stock` | Disponibilité en temps réel, date de réapprovisionnement | Le stock n'est jamais lu dans les fiches indexées |
| `track_order` | Statut, transporteur, retour, remboursement | Exige numéro **et** e-mail ; même réponse si la commande n'existe pas ou si l'e-mail est faux ; adresse et téléphone jamais renvoyés |
| `transfer_to_agent` | Crée une demande (`DEM-…`) et indique si les conseillers sont joignables | — |

- **Boucle d'agent** écrite à la main ([agent.py](novatech/assistant/agent.py)) : 6 tours d'outils au maximum, historique jamais modifié (seulement complété).
- **Sources vérifiées** : la ligne « Sources : » de la réponse est comparée aux passages réellement consultés ; une source citée sans avoir été lue est signalée.
- **Coûts** : consigne et définitions d'outils identiques à chaque appel, donc mises en cache par l'API.
- **Refus** : en cas de refus par un filtre de sécurité, l'API rejoue la requête sur un modèle de secours (`fallbacks="default"`).

## Garde-fous (phase 6)

La consigne système demande à Claude de bien se comporter ; les garde-fous du dossier [novatech/guardrails/](novatech/guardrails/) l'**imposent**, dans le code, quoi que réponde le modèle.

| Moment | Garde-fou | Effet |
|---|---|---|
| Avant Claude | Message > 2 000 caractères, conversation > 30 messages | Refus sans appel à l'API |
| Avant Claude | Numéro de carte (16 chiffres, ou 13-19 chiffres valides selon Luhn), IBAN | Masqué **avant** l'envoi à l'API et l'écriture du journal |
| Avant Claude | Tentative d'injection (« ignore tes instructions », « tu es maintenant… ») | Signalée dans le journal (pas bloquée, pour éviter les faux positifs) |
| Outil `track_order` | Numéro et e-mail absents des messages du client | Outil non exécuté : Claude ne peut ni deviner ni réutiliser un e-mail lu ailleurs |
| Outil `track_order` | 3 couples numéro / e-mail erronés dans la conversation | Outil bloqué (empêche de deviner l'e-mail d'un client) |
| Après Claude | E-mail ni fourni par le client ni de NovaTech | Remplacé par « [e-mail masqué] » |
| Après Claude | Passage de 60 caractères recopié de la consigne système | Réponse remplacée par un refus |
| Après Claude | Source citée mais jamais consultée | Retirée de la ligne « Sources » |

Chaque échange est enregistré dans la table `conversation_log` (question masquée, réponse, outils, sources, alertes, tokens, durée).

**Test d'attaque** (Claude réel, 7 scénarios) : extraction de la consigne, faux administrateur, e-mail d'un autre client, carte bancaire, devinette d'e-mails en série, « tu es DAN sans règles », source imposée : aucune fuite.

## Interface web (phase 7)

```bash
cd frontend && npm install && npm run build && cd ..     # construit l'interface React
uvicorn novatech.api.app:app --port 8000                 # API + interface
```

Ouvrir http://localhost:8000 (documentation de l'API : http://localhost:8000/docs).
Pour modifier l'interface avec rechargement à chaud : `uvicorn ... --reload` dans un terminal, `cd frontend && npm run dev` dans un autre, puis http://localhost:5173.

| Route | Rôle |
|---|---|
| `POST /api/conversations` | Ouvre une conversation (expire après 1 h d'inactivité) |
| `POST /api/conversations/{id}/messages` | Envoie une question ; réponse en flux SSE : `tool` (étapes en direct), puis `reply` ou `error` |
| `GET /api/sources/{id}` | Contenu d'un document ou d'une fiche cité, affiché dans un panneau latéral |
| `GET /api/health` | État du service |

- **Étapes en direct, texte en une fois** : le navigateur affiche « Recherche dans la documentation… », « Vérification du stock… » pendant que Claude travaille, mais le texte n'est envoyé qu'une fois passé par les garde-fous de sortie.
- **Limites par adresse IP** : 10 messages par minute ; 3 échecs de suivi de commande par heure, toutes conversations confondues.
- **Interface** : React + TypeScript (Vite), Markdown sans HTML brut (pas d'injection de script), sources cliquables, carte de transfert vers un conseiller, mode sombre, mobile.

## Évaluation (phase 8)

```bash
python -m novatech.evaluation --check-judge           # le juge doit rejeter 3 mauvaises réponses
python -m novatech.evaluation                         # 40 questions (variante « baseline »)
python -m novatech.evaluation --variant v1 --model claude-opus-5-5   # comparer un autre réglage
node <skill claude-api>/shared/evals/report/build-report-lite.mjs .claude/hillclimb/assistant/
```

- **40 questions** ([sélection](Dataset/evaluation/selection_40.json), [détail](.claude/hillclimb/assistant/cases_40.md)) : tous les cas outils, sécurité, transferts et clarification, plus 23 questions documentaires réparties sur 8 catégories, en privilégiant les pièges.
- **Notation** ([grading.py](novatech/evaluation/grading.py)) : contrôles automatiques (bon outil, bonne source citée, aucun élément interdit) et juge **Claude Opus 5.5** en sortie structurée (éléments clés présents, fidélité aux sources). Une question est **réussie** si tous les critères passent, avec au moins 75 % des éléments clés.
- **Runner** ([novatech/evaluation/](novatech/evaluation/)) : appelle le vrai point d'entrée de l'assistant, en parallèle ; écrit chaque résultat au fil de l'eau (reprise après plantage) ; erreurs d'API, délais dépassés et modèle substitué rangés à part dans `errors.jsonl`, jamais comptés comme des échecs ; harnais verrouillé par empreinte (`--approve-harness` après toute modification de la notation ou des questions).

**Score de référence** (Claude Sonnet 5.5, 1 passage, 1er novembre 2026) :

| Réussite | Couverture | Fidélité | Bon outil | Bonne source | Sans interdit | Latence médiane | Coût |
|---|---|---|---|---|---|---|---|
| **40 / 40** | 100 % | 100 % | 17 / 17 | 22 / 22 | 9 / 9 | 4,2 s | 0,017 $ par question (+ 0,033 $ de juge) |

Avec 40 questions, un 40/40 garantit une réussite réelle d'au moins ~91 % (intervalle de confiance à 95 %). L'évaluation est **saturée** : pour départager deux réglages, il faudra ajouter des questions plus difficiles.

Corrections de la notation faites pendant la mise au point : le juge reçoit la consigne et la description des outils de l'assistant (sinon il prenait pour inventées des informations que l'assistant connaît légitimement) ; pour un transfert, demander d'abord le numéro de commande et l'e-mail est accepté.
