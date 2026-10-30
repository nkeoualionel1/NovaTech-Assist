---
id: mise_a_jour_bios
titre: Mettre à jour le BIOS de la carte mère
type: guide
mise_a_jour: 2026-10-01
---

# Mettre à jour le BIOS de la carte mère

## Faut-il mettre à jour le BIOS ?

Mettez à jour le BIOS uniquement si c'est utile :
- pour installer un **processeur plus récent** que la carte mère ;
- pour corriger une instabilité, notamment avec les profils mémoire XMP/EXPO ;
- si le fabricant publie une mise à jour de sécurité.

Les cartes mères Kairo vendues par NovaTech sont livrées avec un BIOS compatible avec tous les processeurs du catalogue correspondant à leur socket.

## Méthode recommandée : clé USB depuis le BIOS (cartes Kairo)

1. Téléchargez le BIOS correspondant **exactement** à votre modèle de carte mère sur le site du fabricant.
2. Décompressez le fichier et copiez-le sur une **clé USB formatée en FAT32**.
3. Redémarrez et entrez dans le BIOS (touche **Suppr** ou F2 au démarrage).
4. Lancez l'outil de mise à jour intégré (« Kairo Flash ») et sélectionnez le fichier.
5. **Ne coupez surtout pas l'alimentation** pendant la mise à jour (quelques minutes). Le PC peut redémarrer plusieurs fois.

## Mise à jour sans processeur compatible (BIOS Flashback)

Les cartes Kairo X670E Elite, Z790 Elite et Z890 Pro disposent d'un bouton **BIOS Flashback** à l'arrière : il permet de mettre à jour le BIOS **sans processeur ni mémoire installés**, avec la clé USB branchée sur le port USB dédié. Renommez le fichier comme indiqué dans le manuel.

## Après la mise à jour

- Les réglages du BIOS reviennent aux valeurs par défaut : **réactivez le profil XMP/EXPO** et vos autres réglages.
- Le premier démarrage peut être long sur les plateformes DDR5 (entraînement de la mémoire, 2 à 5 minutes).

## En cas de problème

Si le PC ne démarre plus après une coupure pendant la mise à jour, essayez le BIOS Flashback s'il est disponible. Sinon, faites une demande de SAV : sous garantie, une carte mère endommagée par une mise à jour officielle est prise en charge ; l'installation d'un BIOS non officiel n'est pas couverte.
