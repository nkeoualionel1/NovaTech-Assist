"""Phase 6 : garde-fous appliqués par le code autour du modèle."""

from .filtres import (
    detecter_injection,
    emails_autorises,
    masquer_donnees_sensibles,
    nettoyer_reponse,
    sources_citees,
)

# Limites d'usage : protègent des abus et maîtrisent les coûts.
LONGUEUR_MAX_MESSAGE = 2000  # caractères
MESSAGES_MAX_PAR_CONVERSATION = 30
ECHECS_MAX_SUIVI_COMMANDE = 3  # couples numéro / e-mail erronés avant blocage

__all__ = [
    "LONGUEUR_MAX_MESSAGE", "MESSAGES_MAX_PAR_CONVERSATION", "ECHECS_MAX_SUIVI_COMMANDE",
    "detecter_injection", "emails_autorises", "masquer_donnees_sensibles",
    "nettoyer_reponse", "sources_citees",
]
