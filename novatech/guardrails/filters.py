"""Filtres appliqués en dehors du modèle : ils ne dépendent pas de sa bonne volonté.

- Entrée : masquage des données sensibles AVANT envoi à l'API, détection d'injection.
- Sortie : retrait des e-mails et numéros de carte, blocage des fuites de la consigne,
  nettoyage des sources citées.
"""

import re

# 13 à 19 chiffres, éventuellement séparés par des espaces ou des tirets.
CARD_NUMBER_RE = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
COMPANY_EMAIL_DOMAIN = "@novatech-informatique.example"

INJECTION_PATTERNS = [
    r"ignore[rz]?\s+(?:toutes?\s+)?(?:tes|vos|les|ces)\s+(?:instructions|consignes|règles)",
    r"oublie[rz]?\s+(?:toutes?\s+)?(?:tes|vos|les)\s+(?:instructions|consignes|règles)",
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
    r"(?:consigne|prompt|message)\s+(?:système|system)",
    r"system\s+prompt",
    r"(?:tu\s+es|vous\s+êtes)\s+(?:maintenant|désormais)",
    r"mode\s+(?:développeur|developer|admin|debug|dan)\b",
    r"(?:je\s+suis|en\s+tant\s+qu[e'])\s*(?:l'|un\s+)?(?:admin|administrateur|développeur)",
]
INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
SOURCES_LINE_RE = re.compile(r"^\s*\**Sources?\s*:\**\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def is_luhn_valid(digits: str) -> bool:
    """Algorithme de Luhn : distingue un vrai numéro de carte d'un simple nombre long."""
    total = 0
    for i, char in enumerate(reversed(digits)):
        n = int(char)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def mask_sensitive_data(text: str) -> tuple[str, list[str]]:
    """Remplace numéros de carte et IBAN avant que le texte ne quitte le serveur."""
    alerts = []

    def mask_card(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group())
        # 16 chiffres = format Visa / Mastercard : masqué même avec une faute de frappe.
        # Autres longueurs : seulement si Luhn est valide (évite codes-barres, SIRET…).
        if len(digits) == 16 or is_luhn_valid(digits):
            alerts.append("card_number_masked")
            return "[numéro de carte bancaire masqué]"
        return match.group()

    text = CARD_NUMBER_RE.sub(mask_card, text)
    text, iban_count = IBAN_RE.subn("[IBAN masqué]", text)
    if iban_count:
        alerts.append("iban_masked")
    return text, alerts


def detect_injection(text: str) -> bool:
    """Signale une tentative probable de manipulation. On ne bloque pas (risque de faux
    positifs) : on journalise, et la consigne système reste la première défense."""
    return bool(INJECTION_RE.search(text))


def allowed_emails(customer_texts: list[str]) -> set[str]:
    return {email.lower() for text in customer_texts for email in EMAIL_RE.findall(text)}


def sanitize_reply(text: str, customer_texts: list[str], system_prompt: str,
                   valid_sources: set[str]) -> tuple[str, list[str]]:
    """Dernier contrôle avant affichage au client."""
    alerts = []

    if _leaks_system_prompt(text, system_prompt):
        return ("Je ne peux pas partager mes instructions internes. Puis-je vous aider sur une "
                "question concernant NovaTech, vos commandes ou nos produits ?"), ["system_prompt_leak_blocked"]

    # E-mails : seuls ceux donnés par le client et ceux de NovaTech peuvent apparaître.
    allowed = allowed_emails(customer_texts)

    def redact_email(match: re.Match) -> str:
        email = match.group()
        if email.lower() in allowed or email.lower().endswith(COMPANY_EMAIL_DOMAIN):
            return email
        alerts.append("email_redacted")
        return "[e-mail masqué]"

    text = EMAIL_RE.sub(redact_email, text)

    text, card_alerts = mask_sensitive_data(text)
    alerts += card_alerts

    text, removed = _filter_sources_line(text, valid_sources)
    if removed:
        alerts.append("unread_source_removed")
    return text, alerts


def cited_sources(text: str) -> list[str]:
    match = SOURCES_LINE_RE.search(text)
    if not match:
        return []
    return [s.strip(" .*`[]") for s in match.group(1).split(",") if s.strip(" .*`[]")]


def _filter_sources_line(text: str, valid_sources: set[str]) -> tuple[str, list[str]]:
    """Retire de la ligne « Sources : » les identifiants qui n'ont jamais été consultés."""
    cited = cited_sources(text)
    removed = [s for s in cited if s not in valid_sources]
    if not removed:
        return text, []
    kept = [s for s in cited if s in valid_sources]
    replacement = f"Sources : {', '.join(kept)}" if kept else ""
    text = SOURCES_LINE_RE.sub(replacement, text, count=1).rstrip()
    return text, removed


def _leaks_system_prompt(text: str, system_prompt: str, window: int = 60) -> bool:
    """Vrai si la réponse recopie un passage d'au moins `window` caractères de la consigne."""
    def normalize(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().lower()

    text, system_prompt = normalize(text), normalize(system_prompt)
    if len(text) < window:
        return False
    step = window // 2
    return any(system_prompt[i:i + window] in text
               for i in range(0, max(1, len(system_prompt) - window), step))
