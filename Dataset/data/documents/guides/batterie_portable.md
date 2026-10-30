---
id: batterie_portable
titre: Batterie de PC portable – autonomie faible ou ne charge plus
type: guide_depannage
mise_a_jour: 2026-10-01
---

# Batterie de PC portable – autonomie faible ou ne charge plus

## L'autonomie est plus faible que prévu

L'autonomie annoncée est mesurée en usage léger (navigation, luminosité réduite). En jeu, en montage vidéo ou avec la luminosité au maximum, elle peut être divisée par trois ou plus.

Pour l'améliorer :
- Activez le **mode Économiseur d'énergie** et baissez la luminosité.
- Sur les portables équipés d'une carte graphique NVIDIA, laissez le **mode hybride (Optimus)** activé : la carte graphique dédiée ne s'allume que lorsque c'est nécessaire.
- Réduisez la fréquence de l'écran à 60 Hz sur batterie.
- Fermez les applications gourmandes en arrière-plan (Gestionnaire des tâches).

## Vérifier l'état de la batterie

Dans l'invite de commandes, tapez `powercfg /batteryreport` : le rapport généré compare la **capacité actuelle** (« Full charge capacity ») à la **capacité d'origine** (« Design capacity »).

- La batterie est garantie 2 ans. Elle est prise en charge si sa capacité tombe **en dessous de 70 %** de sa capacité d'origine pendant cette période.
- Une perte progressive au-dessus de 70 % correspond à l'usure normale.

## La batterie ne charge plus

1. Vérifiez le **chargeur d'origine**, la prise et le câble ; observez le voyant de charge.
2. Pour un chargeur USB-C, utilisez le port indiqué pour la charge et un chargeur de puissance suffisante.
3. Vérifiez si un **mode de préservation de la batterie** est activé dans le logiciel du fabricant : il limite volontairement la charge à 60 ou 80 % pour prolonger la durée de vie de la batterie. Le message « Branché, ne charge pas » est alors normal.
4. Effectuez une réinitialisation matérielle : chargeur débranché, maintenez le bouton d'allumage 30 secondes.

Si la batterie ne charge toujours pas, faites une demande de SAV.

## Bonnes pratiques

- Évitez de laisser la batterie à 0 % pendant longtemps.
- Pour un portable branché en permanence, activez la limite de charge à 80 %.
- Évitez la chaleur excessive (voiture en été, usage sur un lit).
