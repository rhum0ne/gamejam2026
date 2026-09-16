"""Catalogue des evenements de gameplay.

Ce module ne contient que les noms d'evenements et la forme de leur payload.
Le bus (`event_manager`) et les handlers vivent ailleurs : ajouter un
evenement = une constante ici, un `dispatch`, puis un ou plusieurs `subscribe`.

Usage :

    from src.systems.event_manager import event_manager
    from src.systems.events import PLAYER_DEATH

    event_manager.subscribe(PLAYER_DEATH, on_death)
    event_manager.dispatch(PLAYER_DEATH, {"position": (x, y), "cause": "spikes"})
"""

from __future__ import annotations

# data: {"position": (x, y), "cause": "spikes"|"out_of_bounds"|"enemy"|"sacrifice"|"flame"}
PLAYER_DEATH = "PLAYER_DEATH"

# data: {"reason": "timer"|"manual", "position": (x, y) | None}
PLAYER_GHOST_END = "PLAYER_GHOST_END"

# data: {"level_index": int, "level_name": str, "is_last_level": bool}
PLAYER_WIN = "PLAYER_WIN"
