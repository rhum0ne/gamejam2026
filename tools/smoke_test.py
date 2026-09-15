"""Test de demarrage automatique, sans interaction humaine.

Il verifie que le squelette tourne vraiment : chargement des cartes, creation
de la fenetre, boucle de jeu, passage en mode fantome, retour au corps, logique
de progression. A lancer avant chaque commit et en CI :

    python tools/smoke_test.py

La fenetre est creee en mode invisible (`visible=False`) : aucune fenetre
n'apparait, mais le contexte OpenGL est bien reel, donc `on_draw` est teste.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arcade  # noqa: E402

import settings  # noqa: E402
from src.entities.item import ItemKind  # noqa: E402
from src.systems.event_manager import EventManager  # noqa: E402
from src.systems.events import PLAYER_DEATH, PLAYER_GHOST_END, PLAYER_WIN  # noqa: E402
from src.systems.game_state import GameSession, GameState, PlayView  # noqa: E402
from src.systems.upgrades import SoulProgression  # noqa: E402
from src.ui import keys  # noqa: E402
from src.ui.menus import TitleView, VictoryView  # noqa: E402
from src.world.level import Level  # noqa: E402

FRAME = settings.FRAME_TIME


def check_levels() -> None:
    """Toutes les cartes de la sequence se chargent et sont jouables."""
    for name in settings.LEVEL_SEQUENCE:
        level = Level.from_file(name)
        assert level.player_spawn != (0.0, 0.0), f"{name} : pas de spawn joueur ('P')"
        assert len(level.walls) > 0, f"{name} : aucun mur"
        assert level.width > 0 and level.height > 0
        print(f"  carte '{name}' -> {level.name}: {level.columns}x{level.rows} tuiles, "
              f"{len(level.walls)} murs, {len(level.items)} objets, {len(level.enemies)} ennemis")


def check_progression() -> None:
    """Les paliers d'ames se debloquent tout seuls, sans shop."""
    progression = SoulProgression()
    assert progression.level == 1
    assert progression.ghost_stats.max_range == settings.GHOST_MAX_RANGE
    assert progression.ghost_stats.duration == settings.GHOST_DURATION
    for _ in range(3):
        progression.absorb_orb()
    assert progression.level == 2
    assert progression.ghost_stats.max_range > settings.GHOST_MAX_RANGE
    assert progression.ghost_stats.duration > settings.GHOST_DURATION
    print(f"  progression -> niveau {progression.level}, "
          f"portee fantome {progression.ghost_stats.max_range:.0f} px")


def check_event_manager() -> None:
    """Subscribe / dispatch / unsubscribe fonctionnent dans l'ordre d'abonnement."""
    manager = EventManager()
    received: list[tuple[str, object]] = []

    def first(data: object) -> None:
        received.append(("first", data))

    def second(data: object) -> None:
        received.append(("second", data))

    manager.subscribe(PLAYER_DEATH, first)
    manager.subscribe(PLAYER_DEATH, first)
    manager.subscribe(PLAYER_DEATH, second)
    payload = {"cause": "spikes", "position": (1.0, 2.0)}
    manager.dispatch(PLAYER_DEATH, payload)
    assert received == [("first", payload), ("second", payload)], received

    received.clear()
    manager.unsubscribe(PLAYER_DEATH, first)
    manager.dispatch(PLAYER_DEATH, payload)
    assert received == [("second", payload)], received

    received.clear()
    manager.dispatch(PLAYER_GHOST_END, {"reason": "timer"})
    manager.dispatch(PLAYER_WIN, {"is_last_level": True})
    assert received == [], "un evenement sans abonne ne doit rien declencher"

    manager.clear()
    manager.subscribe(PLAYER_WIN, first)
    manager.clear(PLAYER_WIN)
    manager.dispatch(PLAYER_WIN, {})
    assert received == []
    print("  event_manager -> subscribe, dispatch, unsubscribe, clear OK")


def advance(view: arcade.View, frames: int) -> None:
    for _ in range(frames):
        view.on_update(FRAME)
        view.on_draw()


def check_gameplay_loop(window: arcade.Window) -> None:
    """Boucle corps physique -> mort -> fantome -> retour au corps."""
    view = PlayView(GameSession())
    window.show_view(view)
    assert view.machine.state is GameState.PLAYING

    view.on_key_press(arcade.key.RIGHT, 0)
    advance(view, 30)
    view.on_key_press(arcade.key.LSHIFT, 0)
    view.on_key_release(arcade.key.LSHIFT, 0)
    assert view.player.is_dashing or view.player.dash_ratio < 1.0, "Maj doit declencher le dash"
    advance(view, 12)
    assert not view.player.dash_ready, "le dash doit passer en cooldown"
    view.on_key_release(arcade.key.RIGHT, 0)
    assert view.player.alive, "le joueur ne doit pas mourir en marchant sur le sol"

    view.on_key_press(arcade.key.F, 0)
    view.on_key_release(arcade.key.F, 0)
    assert view.machine.state is GameState.GHOST, "F doit projeter l'esprit"
    assert view.ghost is not None and len(view.level.corpses) == 1

    view.on_key_press(arcade.key.DOWN, 0)
    advance(view, 60)
    view.on_key_release(arcade.key.DOWN, 0)
    assert view.ghost is not None
    assert view.machine.state is GameState.GHOST

    view.ghost.time_left = 0.0
    advance(view, 2)
    assert view.machine.state is GameState.RESPAWNING
    advance(view, int(settings.PLAYER_RESPAWN_DELAY / FRAME) + 5)
    assert view.machine.state is GameState.PLAYING, "le corps doit revenir au checkpoint"
    assert view.player.alive
    print(f"  boucle de jeu -> {view.session.deaths} mort(s), "
          f"etats visites : {' > '.join(state.name for state in view.machine.history)}")


def _camera_y(view: PlayView) -> float:
    return float(view.camera.world.position[1])


def check_vertical_scroll(window: arcade.Window) -> None:
    """Le niveau est plus haut que l'ecran, et la camera suit le fantome en Y."""
    view = PlayView(GameSession())
    window.show_view(view)
    assert view.level.height > settings.SCREEN_HEIGHT, (
        f"le niveau ({view.level.height:.0f} px) doit depasser l'ecran "
        f"({settings.SCREEN_HEIGHT} px) pour tester le defilement vertical"
    )

    start_y = _camera_y(view)
    view.on_key_press(arcade.key.F, 0)
    view.on_key_release(arcade.key.F, 0)
    assert view.ghost is not None

    # Le spawn est en haut du niveau : la camera y est deja clampee.
    # On descend dans le puits, puis on remonte, pour tester les deux axes.
    pit_x = 18 * settings.TILE_SIZE + settings.TILE_SIZE / 2
    for _ in range(300):
        view.held_keys.clear()
        if view.ghost.center_x < pit_x - 6:
            view.held_keys.add(arcade.key.RIGHT)
        elif view.ghost.center_x > pit_x + 6:
            view.held_keys.add(arcade.key.LEFT)
        else:
            view.held_keys.add(arcade.key.DOWN)
        view.ghost.time_left = settings.GHOST_DURATION
        view.on_update(FRAME)
    down_y = _camera_y(view)
    assert down_y < start_y - 20, (
        f"la camera doit descendre dans le puits (sol {start_y:.0f}, puits {down_y:.0f})"
    )

    view.held_keys = {arcade.key.UP}
    for _ in range(200):
        view.ghost.time_left = settings.GHOST_DURATION
        view.on_update(FRAME)
    up_y = _camera_y(view)
    assert up_y > down_y + 40, (
        f"la camera doit remonter avec le fantome (puits {down_y:.0f}, haut {up_y:.0f})"
    )
    print(f"  camera Y -> {start_y:.0f} (sol) / {down_y:.0f} (descente) / {up_y:.0f} (montee), "
          f"monde {view.level.height:.0f} px")


def check_tutorial_is_solvable(window: arcade.Window) -> None:
    """Rejoue la solution attendue du niveau 1 (fiche concept, section 5).

    Corps au bord du puits -> projection de l'esprit -> le fantome plonge
    chercher la cle -> il la ramene au cadavre -> le corps reapparait avec la
    cle -> il franchit le puits et ouvre la porte.

    Ce test protege le level design : si une valeur de `settings.py` (duree du
    fantome, hauteur de saut, largeur du puits) casse la solution, il echoue.
    """
    view = PlayView(GameSession())
    window.show_view(view)
    assert not view.session.knows_esprit
    assert not view._hud_data().show_esprit, "F / esprit ne doit pas apparaitre avant d'avoir ete fantome"

    view.held_keys.add(arcade.key.RIGHT)
    advance(view, 66)
    view.held_keys.clear()
    advance(view, 5)
    assert view.player.alive, "le corps doit s'arreter au bord du puits, pas tomber"
    assert not view._hud_data().show_esprit, "F / esprit ne doit pas spoiler le puits"

    view.on_key_press(arcade.key.F, 0)
    view.on_key_release(arcade.key.F, 0)
    assert view.machine.state is GameState.GHOST
    assert view.session.knows_esprit
    corpse = view.level.corpses[0]
    key_item = next(item for item in view.level.items if item.kind is ItemKind.KEY)

    def fly_to(target_x: float, target_y: float, is_done, limit: int = 600) -> bool:
        """Pilote le fantome vers un point, avec une zone neutre comme un joueur."""
        for _ in range(limit):
            view.held_keys.clear()
            delta_x = target_x() - view.ghost.center_x
            delta_y = target_y() - view.ghost.center_y
            if abs(delta_x) > 6:
                view.held_keys.add(arcade.key.RIGHT if delta_x > 0 else arcade.key.LEFT)
            if abs(delta_y) > 6:
                view.held_keys.add(arcade.key.UP if delta_y > 0 else arcade.key.DOWN)
            # Le timer et la duree de vie du cadavre ne sont pas le sujet de ce test.
            # Le timer du fantome n'est pas le sujet ici : un pilote scripte
            # est bien plus lent qu'un joueur, on le neutralise.
            view.ghost.time_left = settings.GHOST_DURATION
            view.on_update(FRAME)
            if is_done():
                return True
        return False

    assert fly_to(
        lambda: key_item.center_x, lambda: key_item.center_y, lambda: bool(view.ghost.carried)
    ), (
        "le fantome doit pouvoir atteindre la cle au fond du puits"
    )
    # Remontee en deux temps : d'abord au-dessus du cadavre, puis descente
    # dessus, pour ne pas raser la corniche (le fantome bute sur les murs).
    waypoint_y = corpse.center_y + 3 * settings.TILE_SIZE
    assert fly_to(
        lambda: corpse.center_x,
        lambda: waypoint_y,
        lambda: abs(view.ghost.center_x - corpse.center_x) < 12
        and abs(view.ghost.center_y - waypoint_y) < 12,
    ), "le fantome doit pouvoir remonter du puits"
    assert fly_to(
        lambda: corpse.center_x, lambda: corpse.center_y, lambda: bool(view._delivered_items)
    ), "le fantome doit pouvoir ramener la cle jusqu'au cadavre"

    view.ghost.time_left = 0.0
    view.held_keys.clear()
    advance(view, int(settings.PLAYER_RESPAWN_DELAY / FRAME) + 10)
    assert view.player.has_item(ItemKind.KEY), "le corps doit reapparaitre avec la cle livree"
    assert view.machine.state is GameState.PLAYING
    assert view._hud_data().show_esprit, "F / esprit doit apparaitre apres la premiere projection"

    # Le cadavre reste solide au bord du puits et bloque la course d'elan :
    # on attend sa dissipation, comme le ferait un joueur.
    for _ in range(int(settings.CORPSE_LIFETIME / FRAME) + 60):
        if not view.level.corpses:
            break
        view.on_update(FRAME)
    assert not view.level.corpses, "le cadavre doit finir par se dissiper"

    view.held_keys.add(arcade.key.RIGHT)
    previous_x = view.player.center_x
    for _ in range(3500):
        blocked = abs(view.player.center_x - previous_x) < 0.2
        previous_x = view.player.center_x
        wall_probe = (view.player.center_x + 48, view.player.center_y)
        floor_probe = (view.player.center_x + view.player.width / 2 + 28, view.player.bottom - 4)
        wall_ahead = bool(arcade.get_sprites_at_point(wall_probe, view.level.walls))
        hole_ahead = not (
            arcade.get_sprites_at_point(floor_probe, view.level.walls)
            or arcade.get_sprites_at_point(floor_probe, view.level.spectral_walls)
        )
        if view.player.on_ground and (blocked or wall_ahead or hole_ahead):
            view.player.jump()
        view.on_update(FRAME)
        if view.machine.state is GameState.VICTORY:
            break
        if view.machine.state is GameState.GHOST:
            break
    assert view.machine.state is GameState.VICTORY, (
        f"le niveau doit pouvoir etre termine (etat : {view.machine.state.name}, "
        f"x = {view.player.center_x:.0f})"
    )
    print(f"  niveau 1 -> resolu en {view.session.deaths} mort(s), "
          f"porte ouverte a x = {view.player.center_x:.0f}")


def check_menus(window: arcade.Window) -> None:
    """Les vues hors-jeu se dessinent sans erreur, y compris apres un resize."""
    assert keys.is_pressed("q", {arcade.key.LEFT, arcade.key.Q})
    assert keys.is_pressed("z", {arcade.key.UP})
    assert keys.is_pressed("shift", {arcade.key.LSHIFT})
    assert not keys.is_pressed("enter", {arcade.key.ESCAPE})
    assert keys.key_size("space")[0] == keys.key_size("q")[0] * 2
    session = GameSession()
    for view in (TitleView(session), VictoryView(session)):
        window.show_view(view)
        if isinstance(view, TitleView):
            view.held_keys.update({arcade.key.T, arcade.key.SPACE, arcade.key.LSHIFT})
        advance(view, 2)
        view.on_resize(1920, 1080)
        advance(view, 1)
        view.on_resize(settings.SCREEN_MIN_WIDTH, settings.SCREEN_MIN_HEIGHT)
        advance(view, 1)
    play = PlayView(session)
    window.show_view(play)
    assert play.atmosphere.puff_count > 0, "l'atmosphere de premier plan doit etre peuplee"
    play.on_resize(1600, 900)
    play.on_draw()
    visible, total, walls_visible, walls_total = play.level.count_visible_tiles(
        play.camera.visible_rect()
    )
    expected_total = (
        len(play.level.walls) + len(play.level.spectral_walls) + len(play.level.hazards)
    )
    assert total == expected_total
    assert 0 <= visible <= total
    assert 0 <= walls_visible <= walls_total == len(play.level.walls)
    assert 0 < play.level.tiles_drawn < expected_total, (
        f"culling rendu inactif : {play.level.tiles_drawn}/{expected_total} tuiles"
    )
    assert 0 < play.level.chunks_drawn < play.level.chunks_total
    play.on_key_press(arcade.key.F3, 0)
    assert play._debug_enabled is not settings.DEBUG_OVERLAY
    play.on_key_press(arcade.key.F3, 0)
    assert play._debug_enabled is settings.DEBUG_OVERLAY
    play.on_resize(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
    print("  menus -> titre, victoire et resize OK")


def main() -> int:
    print("Project Astral Platformer - smoke test")
    print("[1/6] chargement des cartes")
    check_levels()
    print("[2/6] progression et ameliorations")
    check_progression()
    print("[3/6] event manager")
    check_event_manager()

    window = arcade.Window(
        width=settings.SCREEN_WIDTH,
        height=settings.SCREEN_HEIGHT,
        title="smoke test",
        visible=False,
        vsync=True,
        update_rate=settings.FRAME_TIME,
        draw_rate=settings.FRAME_TIME,
    )
    assert window.vsync
    try:
        print("[3/6] boucle de jeu")
        check_gameplay_loop(window)
        print("[4/6] defilement vertical de la camera")
        check_vertical_scroll(window)
        print("[5/6] solution du niveau tutoriel")
        check_tutorial_is_solvable(window)
        print("[6/6] menus")
        check_menus(window)
    finally:
        window.close()
    print("OK : le squelette demarre et tourne.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
