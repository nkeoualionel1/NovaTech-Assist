"""Filtres appliqués en dehors du modèle : ils ne dépendent pas de sa bonne volonté.

- Entrée : masquage des données sensibles AVANT envoi à l'API, détection d'injection.
- Sortie : retrait des e-mails et numéros de carte, blocage des fuites de la consigne,
  nettoyage des sources citées.
"""

import re

# 13 à 19 chiffres, éventuellement séparés par des espaces ou des tirets.
CARTE = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
DOMAINE_ENTREPRISE = "@novatech-informatique.example"

MOTIFS_INJECTION = [
    r"ignore[rz]?\s+(?:toutes?\s+)?(?:tes|vos|les|ces)\s+(?:instructions|consignes|règles)",
    r"oublie[rz]?\s+(?:toutes?\s+)?(?:tes|vos|les)\s+(?:instructions|consignes|règles)",
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
    r"(?:consigne|prompt|message)\s+(?:système|system)",
    r"system\s+prompt",
    r"(?:tu\s+es|vous\s+êtes)\s+(?:maintenant|désormais)",
    r"mode\s+(?:développeur|developer|admin|debug|dan)\b",
    r"(?:je\s+suis|en\s+tant\s+qu[e'])\s*(?:l'|un\s+)?(?:admin|administrateur|développeur)",
]
INJECTION = re.compile("|".join(MOTIFS_INJECTION), re.IGNORECASE)


def luhn_valide(chiffres: str) -> bool:
    """Algorithme de Luhn : distingue un vrai numéro de carte d'un simple nombre long."""
    total = 0
    for i, c in enumerate(reversed(chiffres)):
        n = int(c)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def masquer_donnees_sensibles(texte: str) -> tuple[str, list[str]]:
    """Remplace numéros de carte et IBAN avant que le texte ne quitte le serveur."""
    alertes = []

    def carte(m: re.Match) -> str:
        chiffres = re.sub(r"\D", "", m.group())
        # 16 chiffres = format Visa / Mastercard : masqué même avec une faute de frappe.
        # Autres longueurs : seulement si Luhn est valide (évite codes-barres, SIRET…).
        if len(chiffres) == 16 or luhn_valide(chiffres):
            alertes.append("carte_bancaire_masquee")
            return "[numéro de carte bancaire masqué]"
        return m.group()

    texte = CARTE.sub(carte, texte)
    texte, n = IBAN.subn("[IBAN masqué]", texte)
    if n:
        alertes.append("iban_masque")
    return texte, alertes


def detecter_injection(texte: str) -> bool:
    """Signale une tentative probable de manipulation. On ne bloque pas (risque de faux
    positifs) : on journalise, et la consigne système reste la première défense."""
    return bool(INJECTION.search(texte))


def emails_autorises(textes_client: list[str]) -> set[str]:
    return {e.lower() for t in textes_client for e in EMAIL.findall(t)}


def nettoyer_reponse(texte: str, textes_client: list[str], consigne: str,
                     sources_valides: set[str]) -> tuple[str, list[str]]:
    """Dernier contrôle avant affichage au client."""
    alertes = []

    if _fuite_consigne(texte, consigne):
        return ("Je ne peux pas partager mes instructions internes. Puis-je vous aider sur une "
                "question concernant NovaTech, vos commandes ou nos produits ?"), ["fuite_consigne_bloquee"]

    # E-mails : seuls ceux donnés par le client et ceux de NovaTech peuvent apparaître.
    autorises = emails_autorises(textes_client)

    def email(m: re.Match) -> str:
        valeur = m.group()
        if valeur.lower() in autorises or valeur.lower().endswith(DOMAINE_ENTREPRISE):
            return valeur
        alertes.append("email_retire")
        return "[e-mail masqué]"

    texte = EMAIL.sub(email, texte)

    texte, alertes_carte = masquer_donnees_sensibles(texte)
    alertes += alertes_carte

    texte, retirees = _filtrer_ligne_sources(texte, sources_valides)
    if retirees:
        alertes.append("source_non_consultee_retiree")
    return texte, alertes


LIGNE_SOURCES = re.compile(r"^\s*\**Sources?\s*:\**\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def sources_citees(texte: str) -> list[str]:
    m = LIGNE_SOURCES.search(texte)
    if not m:
        return []
    return [s.strip(" .*`[]") for s in m.group(1).split(",") if s.strip(" .*`[]")]


def _filtrer_ligne_sources(texte: str, valides: set[str]) -> tuple[str, list[str]]:
    """Retire de la ligne « Sources : » les identifiants qui n'ont jamais été consultés."""
    citees = sources_citees(texte)
    retirees = [s for s in citees if s not in valides]
    if not retirees:
        return texte, []
    gardees = [s for s in citees if s in valides]
    remplacement = f"Sources : {', '.join(gardees)}" if gardees else ""
    texte = LIGNE_SOURCES.sub(remplacement, texte, count=1).rstrip()
    return texte, retirees


def _fuite_consigne(texte: str, consigne: str, longueur: int = 60) -> bool:
    """Vrai si la réponse recopie un passage d'au moins `longueur` caractères de la consigne."""
    normaliser = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    texte, consigne = normaliser(texte), normaliser(consigne)
    if len(texte) < longueur:
        return False
    pas = longueur // 2
    return any(consigne[i:i + longueur] in texte
               for i in range(0, max(1, len(consigne) - longueur), pas))
