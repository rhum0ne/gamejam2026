"""Bus d'evenements : publish / subscribe sans couplage entre systemes.

Un producteur declenche un evenement (`dispatch`) ; les systemes interesses
s'abonnent (`subscribe`) et recoivent le payload. Ajouter un comportement
revient a ecrire une fonction et l'abonner, sans modifier l'emetteur.

Les noms d'evenements sont declares dans `src.systems.events`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

Listener = Callable[[Any], None]


class EventManager:
    """Registre d'abonnements et de declenchements.

    Les callbacks d'un meme evenement sont appeles dans l'ordre d'abonnement.
    `subscribe` est idempotent : deux fois le meme callback ne le lance pas
    deux fois. `dispatch` copie la liste pour qu'un handler puisse se retirer.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Listener]] = defaultdict(list)

    def subscribe(self, event_type: str, callback: Listener) -> None:
        """Abonne `callback` a `event_type`."""
        if not event_type:
            raise ValueError("event_type ne doit pas etre vide")
        if not callable(callback):
            raise TypeError("callback doit etre appelable")
        listeners = self._listeners[event_type]
        if callback not in listeners:
            listeners.append(callback)

    def unsubscribe(self, event_type: str, callback: Listener) -> None:
        """Retire `callback` de `event_type` (no-op s'il n'y est pas)."""
        if not event_type:
            raise ValueError("event_type ne doit pas etre vide")
        listeners = self._listeners.get(event_type)
        if not listeners:
            return
        try:
            listeners.remove(callback)
        except ValueError:
            return

    def dispatch(self, event_type: str, data: Any = None) -> None:
        """Notifie tous les abonnes de `event_type`, avec `data` tel quel."""
        if not event_type:
            raise ValueError("event_type ne doit pas etre vide")
        for callback in list(self._listeners.get(event_type, ())):
            callback(data)

    def clear(self, event_type: str | None = None) -> None:
        """Oublie les abonnements d'un type, ou tous si `event_type` est None."""
        if event_type is None:
            self._listeners.clear()
            return
        if not event_type:
            raise ValueError("event_type ne doit pas etre vide")
        self._listeners.pop(event_type, None)


event_manager = EventManager()
