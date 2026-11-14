"""Compteurs à fenêtre glissante, partagés entre conversations.

Exemple : « au plus 3 échecs de suivi de commande par client et par heure ». La clé est
l'adresse IP côté API, ou l'identifiant de conversation dans le terminal.
En mémoire : suffisant pour un seul processus ; à remplacer par Redis avec plusieurs serveurs.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window_s = window_s
        self._events: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque:
        events = self._events[key]
        while events and now - events[0] > self.window_s:
            events.popleft()
        return events

    def is_exceeded(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.limit

    def record(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def try_acquire(self, key: str) -> bool:
        """Enregistre un événement s'il reste du quota. Renvoie False si la limite est atteinte."""
        with self._lock:
            now = time.monotonic()
            events = self._prune(key, now)
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True
