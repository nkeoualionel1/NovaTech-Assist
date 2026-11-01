# NovaTech Assist – Assistant service client IA (RAG)

Assistant conversationnel pour une enseigne fictive de matériel informatique, **NovaTech Informatique**. Il répond aux clients à partir des documents de l'entreprise (recherche hybride + génération par LLM avec citation des sources) et interroge des outils en temps réel (suivi de commande, stock, transfert vers un conseiller).

> 🚧 Projet en cours – mise en production prévue début décembre 2026.

## Avancement

| Phase | Statut |
|---|---|
| 1. Cadrage (cahier des charges) | ✅ |
| 2. Création des données | ✅ |
| 3. Pipeline d'ingestion | ✅ (voir [README racine](../README.md)) |
| 4. Recherche (retrieval) | ✅ |
| 5. Génération avec Claude | ✅ |
| 6. Garde-fous et sécurité | ✅ |
| 7. Interface | ✅ |
| 8. Évaluation | ⏳ |
| 9–10. Industrialisation et déploiement | ⏳ |

## Stack prévue

Python · FastAPI · Claude API (Anthropic) · PostgreSQL + pgvector · React · Docker · GitHub Actions

## Structure

```
novatech-rag/
├── data/          # Données fictives : catalogue, documents, clients, commandes (voir data/README.md)
├── evaluation/    # Jeu de test : 72 questions avec réponses attendues
└── scripts/       # Génération et validation des données
```

## Régénérer et vérifier les données

Les données sont reproductibles (graine aléatoire fixe). Python 3.10+ suffit, sans dépendance externe.

```bash
python scripts/generate_catalogue.py   # data/catalogue/produits.json
python scripts/generate_commandes.py   # data/commandes/clients.json, commandes.json
python scripts/generate_test_set.py    # evaluation/questions_test.json
python scripts/validate_data.py        # contrôle de cohérence
```

Les documents Markdown de `data/documents/` sont rédigés à la main.

## Données en chiffres

- **100 produits** dans 13 catégories, avec fiches techniques et champs de compatibilité
- **23 documents** : FAQ (36 questions), CGV, livraison, retours, garantie et SAV, paiement, présentation de l'entreprise, 16 guides
- **120 clients** et **200 commandes** couvrant tous les statuts (préparation, assemblage, expédition, livraison, retour, remboursement, annulation)
- **72 questions de test** : RAG, appels d'outils, escalade, refus (hors sujet, injection de prompt, données sensibles)
