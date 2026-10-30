---
id: ecran_bleu_bsod
titre: Écran bleu (BSOD), plantages et redémarrages inattendus
type: guide_depannage
mise_a_jour: 2026-10-01
---

# Écran bleu (BSOD), plantages et redémarrages inattendus

## Noter le code d'erreur

L'écran bleu affiche un **code d'arrêt** (par exemple MEMORY_MANAGEMENT, WHEA_UNCORRECTABLE_ERROR, IRQL_NOT_LESS_OR_EQUAL). Notez-le ou photographiez le QR code : il oriente le diagnostic et vous sera demandé en cas de SAV.

## Causes fréquentes et solutions

| Situation | Piste | Que faire |
|---|---|---|
| Après l'installation d'un pilote ou d'une mise à jour | Pilote incompatible | Désinstallez la mise à jour ou revenez au pilote précédent (Gestionnaire de périphériques → Propriétés → Pilote → Restaurer) |
| Code MEMORY_MANAGEMENT, plantages aléatoires | Mémoire instable | Désactivez le profil XMP/EXPO pour tester ; lancez l'outil « Diagnostic de mémoire Windows » ; testez les barrettes une par une |
| Code WHEA_UNCORRECTABLE_ERROR | Instabilité processeur ou overclocking | Réinitialisez le BIOS aux valeurs par défaut, mettez à jour le BIOS |
| Pendant les jeux uniquement | Carte graphique, alimentation ou températures | Mettez à jour le pilote graphique, vérifiez les températures et la puissance de l'alimentation |
| Au démarrage, en boucle | Fichiers système endommagés | Utilisez la réparation automatique de Windows ou le mode sans échec |

## Réparer Windows

Dans une invite de commandes lancée en tant qu'administrateur :
1. `sfc /scannow` (répare les fichiers système) ;
2. puis `DISM /Online /Cleanup-Image /RestoreHealth`.

## Mode sans échec

Si Windows ne démarre plus : après trois échecs de démarrage consécutifs, Windows ouvre l'**environnement de récupération**. Choisissez Dépannage → Options avancées → Paramètres → Redémarrer → **Mode sans échec** (touche 4). Vous pouvez y désinstaller un pilote ou une mise à jour.

## Si les plantages continuent

Sauvegardez vos données, puis tentez une réinitialisation de Windows (Paramètres → Système → Récupération). Si les écrans bleus persistent après réinitialisation, il s'agit probablement d'un problème matériel : faites une demande de SAV en indiquant les codes d'erreur.
