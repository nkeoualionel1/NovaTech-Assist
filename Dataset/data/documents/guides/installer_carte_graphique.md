---
id: installer_carte_graphique
titre: Installer une carte graphique et ses pilotes
type: guide
mise_a_jour: 2026-10-01
---

# Installer une carte graphique et ses pilotes

## Avant l'achat

Vérifiez trois points (détaillés dans le guide de compatibilité) :
1. La **longueur** de la carte graphique par rapport au boîtier.
2. La **puissance de l'alimentation** conseillée (indiquée sur la fiche produit).
3. Les **connecteurs d'alimentation** disponibles (8 broches PCIe ou 16 broches 12V-2x6).

## Installation

1. Éteignez le PC, débranchez-le et ouvrez le panneau latéral.
2. Retirez les caches métalliques à l'arrière du boîtier correspondant à l'épaisseur de la carte (2 à 3,5 emplacements).
3. Insérez la carte dans le **premier port PCIe x16** (le plus proche du processeur) jusqu'au clic du loquet.
4. Vissez la carte au boîtier. Pour les cartes lourdes (RTX 4080 Super, RX 7900 XTX), installez l'équerre de soutien fournie.
5. Branchez les **câbles d'alimentation** :
   - connecteur 16 broches : enfoncez-le **complètement** (aucun espace visible), sans plier le câble à moins de 3,5 cm du connecteur ;
   - avec l'adaptateur fourni, utilisez des câbles 8 broches **séparés** venant de l'alimentation.
6. Branchez l'écran **sur la carte graphique** et non sur la carte mère.

## Installer les pilotes

1. Si vous remplacez une carte d'une autre marque (AMD ↔ NVIDIA), désinstallez l'ancien pilote, idéalement avec l'outil gratuit DDU en mode sans échec.
2. Téléchargez le pilote **uniquement depuis le site officiel** : NVIDIA (application NVIDIA), AMD (Adrenalin) ou Intel (Arc Control).
3. Installez-le puis redémarrez.

## Cas particulier : Intel Arc B580

Les cartes Intel Arc nécessitent l'activation du **Resizable BAR** (ou « Smart Access Memory » / « Re-Size BAR Support ») dans le BIOS, ainsi que du mode de démarrage UEFI (CSM désactivé). Sans cela, les performances peuvent être fortement réduites.

## Vérifier que tout fonctionne

- Gestionnaire des tâches → Performances → **GPU** : le modèle doit apparaître.
- Dans les jeux, vérifiez que la résolution et la fréquence de l'écran sont correctement réglées.
