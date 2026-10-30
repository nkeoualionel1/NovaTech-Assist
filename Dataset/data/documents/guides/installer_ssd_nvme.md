---
id: installer_ssd_nvme
titre: Installer un SSD NVMe ou SATA et le faire reconnaître
type: guide
mise_a_jour: 2026-10-01
---

# Installer un SSD NVMe ou SATA et le faire reconnaître

## Choisir le bon SSD

- **SSD M.2 NVMe** (Stellar NVMe 500 Go, 1 To, 2 To) : nécessite un emplacement M.2 libre sur la carte mère ou dans le portable (format 2280, le plus courant).
- **SSD SATA 2,5 pouces** (Stellar SATA 1 To) : pour les PC et portables plus anciens sans emplacement M.2 ; se branche avec un câble SATA (données) et un câble d'alimentation SATA.
- Un SSD **PCIe 5.0** fonctionne dans un emplacement PCIe 4.0 ou 3.0, mais à vitesse réduite.

## Installer un SSD M.2 dans un PC de bureau

1. PC éteint et débranché, retirez le **dissipateur M.2** de la carte mère s'il y en a un (et le film protecteur du pad thermique).
2. Insérez le SSD dans l'emplacement M.2 à environ 30°, puis abaissez-le.
3. Fixez-le avec la **vis ou le clip** prévu, puis remettez le dissipateur.
4. Le premier emplacement M.2 (le plus proche du processeur) est en général le plus rapide : utilisez-le pour le SSD système.

## Installer un SSD M.2 dans un PC portable

Ouvrez le capot inférieur (voir le guide d'installation de la mémoire), repérez l'emplacement M.2 libre (indiqué sur la fiche produit, par exemple « 2 emplacements M.2 2280, dont 1 libre »), insérez le SSD puis vissez-le.

## Le SSD n'apparaît pas dans l'Explorateur Windows

C'est normal pour un SSD neuf : il doit être **initialisé** avant utilisation.
1. Clic droit sur le menu Démarrer → **Gestion du disque**.
2. Une fenêtre propose d'initialiser le disque : choisissez **GPT**.
3. Clic droit sur l'espace « Non alloué » → **Nouveau volume simple** → suivez l'assistant (système de fichiers NTFS).

Si le SSD n'apparaît pas du tout dans la Gestion du disque : vérifiez qu'il est bien enfoncé et vissé, et qu'il apparaît dans le BIOS. Sur certaines cartes mères, utiliser un emplacement M.2 désactive des ports SATA (voir le manuel).

## Remplacer le disque système

Pour remplacer le disque contenant Windows sans réinstaller :
- **Clonez** l'ancien disque vers le nouveau avec un logiciel de clonage (souvent fourni gratuitement par le fabricant du SSD), à l'aide d'un boîtier USB externe pour un portable à un seul emplacement.
- Ou réinstallez Windows proprement avec une clé d'installation créée depuis le site de Microsoft. La licence Windows se réactive automatiquement sur le même PC.

Sauvegardez vos données avant toute opération.
