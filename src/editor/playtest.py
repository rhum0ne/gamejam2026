"""Essai d'une carte depuis l'editeur, avec retour par Echap.

La carte doit deja etre enregistree : `PlayView` charge un fichier, pas un
document en memoire. L'editeur sauve tout seul juste avant de lancer l'essai
quand le document a un chemin.
"""

from __future__ import annotations

from collections.abc import Callable

import arcade

from src.editor.document import EditorDocument
from src.systems.game_state import GameSession
from src.ui.display import use_default_camera
from src.ui.menus import open_play_view


def start_playtest(
    window: arcade.Window,
    document: EditorDocument,
    resume: Callable[[], None],
) -> None:
    """Lance le niveau en cours d'edition. `resume` est appele a la sortie."""
    if document.path is None:
        raise ValueError("la carte doit etre enregistree avant l'essai")
    if document.dirty:
        document.save()
    session = GameSession(map_override=document.path.name, on_leave=resume)
    use_default_camera(window)
    open_play_view(window, session)
