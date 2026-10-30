---
id: installer_memoire_ram
titre: Installer ou ajouter de la mémoire vive (RAM) et activer XMP / EXPO
type: guide
mise_a_jour: 2026-10-01
---

# Installer ou ajouter de la mémoire vive (RAM) et activer XMP / EXPO

## Avant d'acheter

- Vérifiez le **type de mémoire** accepté : DDR4 ou DDR5 (voir le guide de compatibilité). Ils ne sont pas interchangeables.
- **PC de bureau : barrettes DIMM. PC portable ou mini PC : barrettes SO-DIMM.**
- Pour un portable, vérifiez sur la fiche produit que la mémoire n'est **pas soudée** et qu'un emplacement est libre (exemples : le Nova Book 16 Pro et l'Orbis Gamer 15 ont 2 emplacements SO-DIMM ; le Nova Book 14 Air et l'Altis Slim 13 ont une mémoire soudée non extensible).
- Pour ajouter de la mémoire à des barrettes existantes, choisissez la **même capacité, la même fréquence et la même latence**. Pour éviter tout souci, le plus simple est de remplacer par un kit complet.

## Installation dans un PC de bureau

1. Éteignez le PC, débranchez-le et touchez une partie métallique du boîtier pour vous décharger de l'électricité statique.
2. Ouvrez les clips des emplacements mémoire.
3. Avec **deux barrettes**, utilisez les emplacements **A2 et B2** (en général les 2e et 4e en partant du processeur) : vérifiez dans le manuel de la carte mère.
4. Alignez l'encoche de la barrette avec celle de l'emplacement et appuyez fermement des deux côtés **jusqu'au clic**.
5. Refermez et redémarrez. Avec de la DDR5, le premier démarrage peut prendre **2 à 5 minutes** (entraînement de la mémoire) : l'écran reste noir pendant ce temps, c'est normal.

## Installation dans un PC portable

1. Éteignez complètement le portable (maintenez Maj en cliquant sur « Arrêter »), débranchez le chargeur.
2. Retirez les vis du capot inférieur et ouvrez-le délicatement avec un outil en plastique.
3. Si le fabricant le recommande, débranchez la batterie.
4. Insérez la barrette SO-DIMM à 30° puis abaissez-la jusqu'à ce que les clips latéraux se referment.

Ajouter de la mémoire n'annule pas la garantie, à condition que l'intervention soit réalisée correctement.

## Activer le profil XMP ou EXPO (PC de bureau)

Par défaut, la mémoire fonctionne à une fréquence réduite (par exemple 4800 MT/s pour de la DDR5 vendue 6000 MT/s). Pour obtenir la fréquence annoncée :

1. Au démarrage, appuyez sur **Suppr** (ou F2) pour entrer dans le BIOS.
2. Activez le profil **EXPO** (cartes AMD) ou **XMP** (cartes Intel), par exemple « EXPO I » ou « XMP Profile 1 ».
3. Enregistrez et redémarrez (F10).

Le kit Velox DDR5 32 Go 6000 CL30 est compatible EXPO et XMP 3.0. Si le PC devient instable après activation, mettez à jour le BIOS ou revenez aux réglages par défaut.

## Vérifier que la mémoire est reconnue

Gestionnaire des tâches (Ctrl + Maj + Échap) → onglet **Performances** → **Mémoire** : la capacité totale et la vitesse s'affichent.
