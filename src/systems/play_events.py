"""Handlers de PlayView branches sur le bus d'evenements.

PlayView se contente de `dispatch` ; les consequences (cadavre, fantome,
victoire) sont ici, une fonction par comportement. Pour en ajouter un :
ecrire une fonction et l'abonner dans `bind_play_view`.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import settings
from src.entities.corpse import Corpse
from src.entities.ghost import Ghost
from src.systems.event_manager import event_manager
from src.systems.events import PLAYER_DEATH, PLAYER_GHOST_END, PLAYER_WIN
from src.ui.sfx import play_ghost_end, play_ghost_start, play_level_win

if TYPE_CHECKING:
    from src.systems.game_state import PlayView


def bind_play_view(view: PlayView) -> None:
    """Abonne les comportements de `view` aux evenements de gameplay.

    `clear()` evite de conserver les handlers d'une PlayView precedente
    (changement de vue, smoke test) sur le singleton `event_manager`.
    """
    event_manager.clear()
    event_manager.subscribe(PLAYER_DEATH, partial(on_player_death_immobilize, view))
    event_manager.subscribe(PLAYER_DEATH, partial(on_player_death_spawn_corpse, view))
    event_manager.subscribe(PLAYER_DEATH, partial(on_player_death_enter_ghost, view))
    event_manager.subscribe(PLAYER_GHOST_END, partial(on_player_ghost_end, view))
    event_manager.subscribe(PLAYER_WIN, partial(on_player_win, view))


def emit_player_death(view: PlayView, cause: str) -> None:
    from src.systems.game_state import GameState

    if settings.PLAYER_INVINCIBLE and cause != "sacrifice":
        return
    if not view.machine.can(GameState.GHOST):
        return
    event_manager.dispatch(
        PLAYER_DEATH,
        {"position": (view.player.center_x, view.player.center_y), "cause": cause},
    )


def emit_ghost_end(view: PlayView, reason: str) -> None:
    from src.systems.game_state import GameState

    if not view.machine.can(GameState.RESPAWNING):
        return
    position = None if view.ghost is None else (view.ghost.center_x, view.ghost.center_y)
    event_manager.dispatch(PLAYER_GHOST_END, {"reason": reason, "position": position})


def emit_player_win(view: PlayView) -> None:
    from src.systems.game_state import GameState

    if not view.machine.can(GameState.VICTORY):
        return
    event_manager.dispatch(
        PLAYER_WIN,
        {
            "level_index": view.session.level_index,
            "level_name": view.level.name,
            "is_last_level": view.session.is_last_level,
        },
    )


def on_player_death_immobilize(view: PlayView, data: dict) -> None:
    """Compte la mort et fige le corps physique."""
    view.session.deaths += 1
    view.player.die()


def on_player_death_spawn_corpse(view: PlayView, data: dict) -> None:
    """Laisse un cadavre solide a l'endroit de la mort."""
    center_x, center_y = data["position"]
    corpse = Corpse(center_x, center_y, facing=view.player.facing)
    corpse.bind_world(view._static_platforms())
    view.level.spawn_corpse(corpse)
    view.anchor_corpse = corpse


def on_player_death_enter_ghost(view: PlayView, data: dict) -> None:
    """Projette l'esprit et passe en mode fantome."""
    from src.systems.game_state import GameState

    corpse = view.anchor_corpse
    spawn_x, spawn_y = data["position"]
    if corpse is not None:
        spawn_x, spawn_y = corpse.center_x, corpse.center_y
    stats = view.session.progression.ghost_stats
    view.ghost = Ghost(spawn_x, spawn_y, stats, anchor=(spawn_x, spawn_y))
    view.ghost.bind_world(view.level.ghost_walls)
    view.session.knows_esprit = True
    play_ghost_start()
    view.start_ghost_emergence(spawn_x, spawn_y)
    view.machine.to(GameState.GHOST)


def on_player_ghost_end(view: PlayView, data: dict) -> None:
    """Fin du mode fantome : le corps revient au dernier checkpoint."""
    from src.systems.game_state import GameState

    if view.ghost is not None:
        for item in view.ghost.release_all():
            item.drop_at(item.center_x, item.center_y)
        view.ghost.start_vanish()
    play_ghost_end()
    for wall in view.level.spectral_walls:
        wall.set_revealed(False)
    view.anchor_corpse = None
    respawn_x, respawn_y = view.player.respawn_point
    view.start_player_rebirth(respawn_x, respawn_y)
    view.machine.try_to(GameState.RESPAWNING)


def on_player_win(view: PlayView, data: dict) -> None:
    """Niveau reussi : ecran de victoire (suivant / reessayer / niveaux)."""
    from src.systems.game_state import GameState
    from src.ui.menus import VictoryView

    play_level_win()
    view.machine.try_to(GameState.VICTORY)
    view.window.show_view(VictoryView(view.session))
