---
id: guide_compatibilite_composants
titre: Guide de compatibilité des composants PC
type: guide
mise_a_jour: 2026-10-01
---

# Guide de compatibilité des composants PC

Avant d'acheter un composant pour monter ou faire évoluer un PC, vérifiez ces six points. Le configurateur NovaTech les contrôle automatiquement.

## 1. Processeur et carte mère : le socket

Le processeur et la carte mère doivent avoir **le même socket**.

| Socket | Processeurs (exemples au catalogue) | Chipsets compatibles | Mémoire |
|---|---|---|---|
| AM4 | AMD Ryzen 5 5600 | A520, B550 | DDR4 uniquement |
| AM5 | AMD Ryzen 5 7600, Ryzen 7 7800X3D, Ryzen 9 7950X | B650, X670E | DDR5 uniquement |
| LGA1700 | Intel Core i3-14100, i5-14400F, i5-14600K, i7-14700K | B760, Z790 | DDR4 **ou** DDR5 selon la carte mère |
| LGA1851 | Intel Core Ultra 7 265K | Z890 | DDR5 uniquement |

Points d'attention :
- **LGA1700 et LGA1851 ne sont pas compatibles entre eux** : un Core Ultra 200S ne se monte pas sur une carte mère B760 ou Z790.
- Un processeur AM4 ne se monte pas sur une carte AM5, et inversement.
- **Overclocking** : les processeurs Intel « K » ne peuvent être overclockés que sur une carte mère Z790 (ou Z890 pour le LGA1851). Sur une B760, ils fonctionnent normalement, sans overclocking.

## 2. Mémoire vive : DDR4 ou DDR5

- La mémoire **DDR4 et DDR5 ne sont pas interchangeables** : les encoches sont différentes. Une barrette DDR5 ne rentre pas dans un emplacement DDR4.
- Sur LGA1700, vérifiez la fiche de la carte mère : la Kairo B760M DDR4 accepte uniquement la DDR4, tandis que la Kairo B760 DDR5 Gaming et la Kairo Z790 Elite acceptent uniquement la DDR5.
- **PC de bureau = barrettes DIMM ; PC portable et mini PC = barrettes SO-DIMM** (plus courtes). Elles ne sont pas interchangeables.
- Respectez la capacité maximale et le nombre d'emplacements de la carte mère (par exemple 2 emplacements et 64 Go maximum pour la Kairo A520M Basic).
- Préférez un **kit de 2 barrettes identiques** pour profiter du double canal.

## 3. Format de la carte mère et du boîtier

Le boîtier doit accepter le format de la carte mère :

| Boîtier | Formats de carte mère acceptés |
|---|---|
| Forma Mini ITX | mini-ITX uniquement |
| Forma Compact M | micro-ATX, mini-ITX |
| Forma Air ATX, Forma Glass RGB | ATX, micro-ATX, mini-ITX |
| Forma Tower XL | E-ATX, ATX, micro-ATX, mini-ITX |

Une carte mère ATX **ne rentre pas** dans un boîtier micro-ATX ou mini-ITX. Une carte plus petite rentre dans un boîtier plus grand.

## 4. Carte graphique : longueur et puissance de l'alimentation

- **Longueur** : la longueur de la carte graphique doit être inférieure à la longueur maximale acceptée par le boîtier (exemple : la Vertex RTX 4080 Super mesure 340 mm ; elle rentre dans le Forma Air ATX, 380 mm maximum, mais pas dans le Forma Mini ITX, 320 mm maximum).
- **Puissance** : respectez la puissance d'alimentation conseillée par le fabricant de la carte graphique (indiquée sur chaque fiche) : 550 W pour une RTX 4060 ou une RX 7600, 650 W pour une RTX 4070 Super, 700 W pour une RX 7800 XT, 750 W pour une RTX 4080 Super, 850 W pour une RX 7900 XTX.
- **Connecteurs** : vérifiez que l'alimentation dispose des bons câbles. Les cartes RTX 4070 Super et RTX 4080 Super utilisent un connecteur 16 broches 12V-2x6 ; un adaptateur est fourni, mais une alimentation ATX 3.1 avec câble natif (Voltis 750 W, 850 W ou 1000 W ATX 3.1) est recommandée. La RX 7900 XTX nécessite **trois** connecteurs 8 broches.
- **Graphique intégré** : les processeurs AMD Ryzen 5 5600 et Intel Core i5-14400F (version « F ») n'ont pas de puce graphique intégrée. Une carte graphique dédiée est alors obligatoire pour avoir une image.

## 5. Refroidissement du processeur

- Certains processeurs sont livrés **sans ventirad** : Ryzen 7 7800X3D, Ryzen 9 7950X, Core i5-14600K, Core Ultra 7 265K. Prévoyez un ventirad ou un watercooling.
- **Hauteur du ventirad** : elle doit être inférieure à la hauteur maximale du boîtier (le Polar Tower 120 mesure 155 mm : il rentre dans le Forma Compact M, 160 mm maximum, mais pas dans le Forma Mini ITX, 65 mm maximum ; pour ce dernier, choisissez le Polar Low Profile 47).
- **Watercooling (AIO)** : vérifiez que le boîtier accepte la taille du radiateur (240 mm ou 360 mm). Le Forma Mini ITX n'accepte pas de radiateur.
- **Puissance dissipée** : choisissez un refroidissement dont le TDP maximal dépasse celui du processeur (le Ryzen 9 7950X, 170 W, demande au minimum un AIO 240 mm ; un AIO 360 mm est conseillé).

## 6. Alimentation et boîtier

- Les boîtiers ATX acceptent les alimentations au format ATX.
- Le **Forma Mini ITX** n'accepte que les alimentations **SFX** (exemple : Voltis SFX 750 W).
- Pour calculer la puissance nécessaire, additionnez la consommation du processeur et de la carte graphique, puis ajoutez environ 150 W de marge, ou suivez simplement la recommandation du fabricant de la carte graphique.

## Stockage : SSD M.2 NVMe, SATA et disques durs

- Un SSD **M.2 2280 NVMe** se monte dans un emplacement M.2 de la carte mère (vérifiez le nombre d'emplacements libres).
- Un SSD **PCIe 5.0** (Stellar NVMe 2 To PCIe 5.0) fonctionne dans un emplacement PCIe 4.0, mais à vitesse réduite. Pour profiter de son plein débit, il faut un emplacement M.2 PCIe 5.0 (cartes Kairo X670E Elite, Z790 Elite, Z890 Pro).
- Les SSD SATA 2,5 pouces et disques durs 3,5 pouces se branchent sur un port SATA et à l'alimentation.
