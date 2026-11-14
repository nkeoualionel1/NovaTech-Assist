"""Phase 6 : garde-fous appliqués par le code autour du modèle."""

from .filters import (
    allowed_emails,
    cited_sources,
    detect_injection,
    mask_sensitive_data,
    sanitize_reply,
)

# Limites d'usage : protègent des abus et maîtrisent les coûts.
MAX_MESSAGE_LENGTH = 2000  # caractères
MAX_MESSAGES_PER_CONVERSATION = 30
MAX_ORDER_LOOKUP_FAILURES = 3  # couples numéro / e-mail erronés avant blocage…
ORDER_LOOKUP_WINDOW_S = 3600  # …par client (IP) et par heure, toutes conversations confondues

__all__ = [
    "MAX_MESSAGE_LENGTH", "MAX_MESSAGES_PER_CONVERSATION", "MAX_ORDER_LOOKUP_FAILURES",
    "ORDER_LOOKUP_WINDOW_S", "allowed_emails", "cited_sources", "detect_injection",
    "mask_sensitive_data", "sanitize_reply",
]
