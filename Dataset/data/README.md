# Données du projet NovaTech Informatique

Toutes les données sont **fictives** et générées pour la démonstration : entreprise, marques (Nova, Orbis, Altis, Lumen, Kairo, Velox, Vertex, Stellar, Voltis, Forma, Polar, Keyra, Sonik, Netix), clients, adresses e-mail (`@example.com`) et commandes. Les processeurs et cartes graphiques sont de vraies références du marché, avec leurs caractéristiques principales, pour que les questions de compatibilité restent réalistes.

Date de référence du jeu de données : **30 octobre 2026, midi**.

## Contenu

```
data/
├── catalogue/
│   └── produits.json          100 produits, 13 catégories (fiches techniques + champs de compatibilité)
├── documents/                 Base documentaire indexée par le RAG (Markdown + front-matter)
│   ├── entreprise_contact.md  Présentation, contact, horaires, services (NovaPoints, configurateur, reprise…)
│   ├── livraison.md           Zones, modes, délais, tarifs et seuils de gratuité
│   ├── retours_remboursements.md
│   ├── garantie_sav.md        Garantie légale, fabricant, NovaCare+, procédure SAV
│   ├── paiement.md            Moyens de paiement, paiement en plusieurs fois, factures
│   ├── cgv.md                 Conditions générales de vente
│   ├── faq.md                 36 questions/réponses
│   └── guides/                16 guides : compatibilité des composants + 15 guides de dépannage et d'installation
└── commandes/                 Données utilisées par les OUTILS (pas indexées par le RAG)
    ├── clients.json           120 clients
    └── commandes.json         200 commandes (25/08 → 30/10/2026)
```

## Où va chaque donnée ?

| Donnée | Utilisation |
|---|---|
| `documents/*.md` | Découpés en passages, vectorisés et indexés → **recherche RAG** |
| `catalogue/produits.json` | Une fiche par produit indexée → **recherche RAG** ; le stock est lu en direct par l'outil `verifier_stock()` |
| `commandes/*.json` | Chargés en base SQL → outil `suivi_commande(numero, email)`, **jamais indexés** (données personnelles) |
| `../evaluation/questions_test.json` | 72 questions avec réponses attendues → **évaluation** |

## Format des documents

Chaque document commence par un front-matter YAML :

```yaml
---
id: livraison                 # identifiant unique = nom du fichier, cité comme source
titre: Livraison – modes, délais et frais
type: politique               # politique | faq | juridique | information | guide | guide_depannage
mise_a_jour: 2026-10-01
---
```

## Statuts de commande

`en_attente_paiement` · `en_preparation` · `en_assemblage` · `expediee` · `en_cours_de_livraison` · `disponible_retrait` · `livree` · `annulee` · `retour_en_cours` · `retour_rembourse`

## Pièges volontaires (pour tester l'assistant)

- **Ruptures de stock** avec date de réapprovisionnement : Ryzen 7 7800X3D, RTX 4080 Super, Orbis Gamer 16, écran OLED 240 Hz, routeur Wi-Fi 7.
- **Mémoire soudée** sur certains portables (Nova Book 14 Air, Altis Slim 13, Altis Creator 16 OLED…).
- **USB-C sans Thunderbolt** (Orbis Gamer 15) et **USB-C sans vidéo** (Nova Book 14 Student).
- **Processeurs sans graphique intégré** (Ryzen 5 5600, Core i5-14400F).
- **Carte mère LGA1700 en DDR4** (Kairo B760M DDR4) à côté de modèles DDR5.
- **Sockets incompatibles** LGA1700 / LGA1851.
- **Seuils de livraison différents** en France (99 €) et en Belgique/Luxembourg (150 €).
- **Réduction étudiante** limitée aux PC portables, **PC sur mesure** non retournables.
