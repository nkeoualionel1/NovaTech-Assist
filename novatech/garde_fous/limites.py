"""Compteurs à fenêtre glissante, partagés entre conversations.

Exemple : « au plus 3 échecs de suivi de commande par client et par heure ». La clé est
l'adresse IP côté API, ou l'identifiant de conversation dans le terminal.
En mémoire : suffisant pour un seul processus ; à remplacer par Redis avec plusieurs serveurs.
"""

import threading
import time
from collections import defaultdict, deque


class Limiteur:
    def __init__(self, maximum: int, fenetre_s: float):
        self.maximum = maximum
        self.fenetre_s = fenetre_s
        self._evenements: dict[str, deque] = defaultdict(deque)
        self._verrou = threading.Lock()

    def _purger(self, cle: str, maintenant: float) -> deque:
        file = self._evenements[cle]
        while file and maintenant - file[0] > self.fenetre_s:
            file.popleft()
        return file

    def depasse(self, cle: str) -> bool:
        with self._verrou:
            return len(self._purger(cle, time.monotonic())) >= self.maximum

    def enregistrer(self, cle: str) -> None:
        with self._verrou:
            maintenant = time.monotonic()
            self._purger(cle, maintenant).append(maintenant)

    def consommer(self, cle: str) -> bool:
        """Enregistre un événement s'il reste du quota. Renvoie False si la limite est atteinte."""
        with self._verrou:
            maintenant = time.monotonic()
            file = self._purger(cle, maintenant)
            if len(file) >= self.maximum:
                return False
            file.append(maintenant)
            return True
