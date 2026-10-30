---
id: ecran_noir_pas_d_affichage
titre: Écran noir – le PC s'allume mais aucune image
type: guide_depannage
mise_a_jour: 2026-10-01
---

# Écran noir – le PC s'allume mais aucune image

Les ventilateurs tournent et les voyants s'allument, mais l'écran reste noir ou affiche « Pas de signal ».

## 1. Vérifier le branchement de l'écran

- **Avec une carte graphique dédiée, branchez l'écran sur la carte graphique** (ports situés en bas, à l'horizontale, à l'arrière du PC), et non sur les sorties vidéo de la carte mère.
- Avec un processeur **sans graphique intégré** (AMD Ryzen 5 5600, Intel Core i5-14400F ou tout modèle « F »), les sorties vidéo de la carte mère ne fonctionnent pas du tout.
- Vérifiez la **source d'entrée** sélectionnée sur l'écran (HDMI 1, HDMI 2, DisplayPort) avec les boutons de l'écran.
- Essayez un autre câble ou un autre port (HDMI au lieu de DisplayPort).

## 2. Premier démarrage d'un PC DDR5 : patientez

Lors du **premier démarrage** d'un PC équipé de mémoire DDR5 (plateformes AM5 et Intel DDR5), ou après l'ajout de mémoire ou une mise à jour du BIOS, la carte mère effectue un **entraînement de la mémoire** (« memory training »). L'écran peut rester noir **jusqu'à 2 à 5 minutes**. N'éteignez pas le PC pendant cette étape.

## 3. Mémoire et carte graphique

- Si vous avez ajouté ou déplacé de la mémoire : vérifiez que les barrettes sont **enfoncées jusqu'au clic** des deux côtés, dans les emplacements conseillés par le manuel (en général A2 et B2 pour deux barrettes).
- Vérifiez que la carte graphique est bien enfoncée dans le premier port PCIe x16 et que **tous ses câbles d'alimentation** sont branchés (8 broches ou 16 broches).
- Observez les **voyants de diagnostic** de la carte mère (CPU, DRAM, VGA, BOOT) : le voyant resté allumé indique l'élément en cause.

## 4. PC portable sans image

- Branchez un écran externe : si l'image s'affiche, le problème vient de l'écran du portable ou de sa nappe → demande de SAV.
- Essayez le raccourci **Windows + Ctrl + Maj + B**, qui réinitialise le pilote graphique.
- Vérifiez que la luminosité n'est pas au minimum.

## Toujours en panne ?
Faites une demande de SAV depuis votre espace client en indiquant les voyants observés et les étapes déjà testées.
