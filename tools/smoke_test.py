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
from src.entities.enemy import Enemy, EnemyState  # noqa: E402
from src.entities.item import ItemKind  # noqa: E402
from src.entities.player import Player  # noqa: E402
from src.systems import collisions  # noqa: E402
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
        extra = ""
        if name == "level_1_tuto.json":
            assert len(level.mechanisms) >= 1, f"{name} : plaque d'activation manquante"
            hanging = sum(1 for hazard in level.hazards if getattr(hazard, "hanging", False))
            assert hanging >= 1, f"{name} : pique de plafond manquante"
            extra = f", {len(level.mechanisms)} plaque(s), {hanging} pique(s) plafond"
        print(f"  carte '{name}' -> {level.name}: {level.columns}x{level.rows} tuiles, "
              f"{len(level.walls)} murs, {len(level.items)} objets, {len(level.enemies)} ennemis{extra}")


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


def check_enemy_ai() -> None:
    """Portee d'aggro verticale, coup d'epee (seul mortel), esquive, mort animee.

    Construit `Enemy`/`Player` isoles (sans niveau ni fenetre : creer un
    sprite ne demande pas de contexte OpenGL, seul le dessin en a besoin, cf.
    agents.md section 9).
    """
    enemy = Enemy(200.0, 200.0)

    # Joueur tres au-dessus (hors ENEMY_AGGRO_VERTICAL_RANGE) mais proche
    # horizontalement : l'ennemi ne doit pas le suivre, il est inatteignable.
    player = Player(200.0, 200.0 + settings.ENEMY_AGGRO_VERTICAL_RANGE + 40.0)
    enemy.update(FRAME, player=player, corpses=None)
    assert enemy.state is EnemyState.PATROL, "trop haut : l'ennemi ne doit pas suivre"

    # Meme niveau, a portee d'aggro mais hors de portee de melee : poursuite.
    player.center_y = enemy.center_y
    player.center_x = enemy.center_x + settings.ENEMY_AGGRO_RANGE - 10.0
    enemy.update(FRAME, player=player, corpses=None)
    assert enemy.state is EnemyState.CHASE, "a portee et au meme niveau : doit poursuivre"
    assert enemy.change_x != 0.0

    # Approche a portee de melee : l'ennemi s'arrete et arme son coup.
    player.center_x = enemy.center_x + settings.ENEMY_ATTACK_RANGE - 5.0
    enemy.update(FRAME, player=player, corpses=None)
    assert enemy.state is EnemyState.ATTACK, "assez proche : doit s'arreter pour frapper"
    assert enemy.change_x == 0.0, "l'ennemi ne doit pas glisser pendant l'attaque"

    # Toucher le corps ne tue pas : joueur colle contre l'ennemi pendant l'armement.
    player.center_x = enemy.center_x + 10.0
    assert arcade.check_for_collision(enemy, player), "le joueur doit chevaucher le corps"
    assert collisions.enemy_striking_player(player, [enemy]) is None, (
        "le simple contact avec le corps ne doit pas tuer"
    )

    # Joueur immobile a portee : la lame finit par le toucher, apres l'armement.
    frames_to_hit = None
    for frame in range(120):
        enemy.update(FRAME, player=player, corpses=None)
        if collisions.enemy_striking_player(player, [enemy]) is enemy:
            frames_to_hit = frame + 1
            break
    assert frames_to_hit is not None, "un joueur immobile a portee doit etre touche par le coup"
    assert frames_to_hit > 5, "le coup doit etre annonce (armement) avant de toucher"

    # Esquive : le joueur recule hors de portee de la lame pendant l'armement.
    dodger = Enemy(200.0, 200.0)
    player.center_x = dodger.center_x + settings.ENEMY_ATTACK_RANGE - 5.0
    player.center_y = dodger.center_y
    dodger.update(FRAME, player=player, corpses=None)
    assert dodger.state is EnemyState.ATTACK
    player.center_x = dodger.center_x + settings.ENEMY_ATTACK_REACH + 10.0
    for _ in range(120):
        dodger.update(FRAME, player=player, corpses=None)
        assert collisions.enemy_striking_player(player, [dodger]) is None, (
            "hors de portee de la lame : le coup doit rater"
        )
        if dodger.state is not EnemyState.ATTACK:
            break
    assert dodger.state is EnemyState.CHASE, "coup fini, joueur recule : doit reprendre la poursuite"

    # Mort : bille bleue, etat DYING, un 2e coup pendant DYING est ignore.
    orb = enemy.take_damage()
    assert orb is not None, "take_damage doit renvoyer une bille bleue a la mort"
    assert enemy.state is EnemyState.DYING
    assert enemy.take_damage() is None, "un ennemi DYING ignore les coups suivants"
    assert collisions.enemy_striking_player(player, [enemy]) is None, (
        "un ennemi qui meurt en plein coup ne doit plus tuer"
    )
    for _ in range(120):
        enemy.update(FRAME, player=player, corpses=None)
    assert enemy._animator.finished, "l'animation de mort doit se terminer"

    print(f"  IA ennemie -> aggro vertical, contact inoffensif, coup a {frames_to_hit} frames, "
          "esquive, mort animee OK")


def advance(view: arcade.View, frames: int) -> None:
    for _ in range(frames):
        view.on_update(FRAME)
        view.on_draw()


def wait_ghost_ready(view: PlayView, limit: int = 180) -> None:
    """Laisse finir le gros plan / l'emergence avant de piloter le fantome."""
    for _ in range(limit):
        if not view.ghost_emerging:
            return
        view.on_update(FRAME)
        view.on_draw()
    raise AssertionError("la transition mort -> fantome n'est pas terminee")


def wait_rebirth_ready(view: PlayView, limit: int = 180) -> None:
    """Laisse finir le voile noir / la reconstruction avant de piloter le corps."""
    for _ in range(limit):
        if view.machine.state is GameState.PLAYING and not view.player_rebirthing:
            return
        view.on_update(FRAME)
        view.on_draw()
    raise AssertionError("la transition fantome -> corps n'est pas terminee")


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
    assert view.ghost_emerging, "la mort doit ouvrir une cinematique"
    wait_ghost_ready(view)
    assert not view.ghost_emerging

    view.on_key_press(arcade.key.DOWN, 0)
    advance(view, 60)
    view.on_key_release(arcade.key.DOWN, 0)
    assert view.ghost is not None
    assert view.machine.state is GameState.GHOST

    view.ghost.time_left = 0.0
    advance(view, 2)
    assert view.machine.state is GameState.RESPAWNING
    assert view.player_rebirthing, "la fin du fantome doit ouvrir une cinematique"
    wait_rebirth_ready(view)
    assert view.machine.state is GameState.PLAYING, "le corps doit revenir au checkpoint"
    assert view.player.alive
    assert not view.player_rebirthing
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
    wait_ghost_ready(view)

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
    wait_ghost_ready(view)
    corpse = view.level.corpses[0]
    key_item = next(item for item in view.level.items if item.kind is ItemKind.KEY)
    view.on_update(FRAME)
    view.on_draw()
    assert view.level.mechanisms, "le tutoriel doit contenir une plaque d'activation"
    assert view.level.mechanisms[0].pressed, (
        "le cadavre au bord du puits doit enfoncer la plaque "
        f"(corpse x={corpse.center_x:.0f}, plate x={view.level.mechanisms[0].plate.center_x:.0f})"
    )
    assert all(tile.hidden for tile in view.level.mechanisms[0].targets), (
        "la plaque doit ouvrir le passage du puits tant que le cadavre appuie"
    )

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
    wait_rebirth_ready(view)
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


def check_editor_document() -> None:
    """Le modele d'edition charge une carte, peint, annule, refait, reecrit."""
    import json
    import tempfile

    from src.editor import palette
    from src.editor.document import EditorDocument
    from src.editor.selection import GridRect
    from src.world.level import gameplay_kinds

    kinds = {item.kind for item in palette.PALETTE}
    for kind in gameplay_kinds():
        assert kind in kinds, f"la palette doit lister le gameplay '{kind}'"
    assert "rock" in kinds and "enemy" in kinds and "spike" in kinds

    document = EditorDocument.from_file("level_1_tuto.json")
    assert document.columns > 0 and document.rows > 0
    assert document.counts().get("player_spawn", 0) >= 1

    column, row = 4, 4
    before = document.cell(column, row)
    painted = document.paint(((column, row),), "spike")
    assert painted
    assert document.cell(column, row) == "spike"
    document.undo()
    assert document.cell(column, row) == before
    document.redo()
    assert document.cell(column, row) == "spike"
    document.undo()

    rect = GridRect(2, 2, 6, 5)
    document.fill_rect(rect, "grass")
    for cell_column, cell_row in rect.cells():
        assert document.cell(cell_column, cell_row) == "grass"
    document.replace_kind("grass", "rock", rect)
    for cell_column, cell_row in rect.cells():
        assert document.cell(cell_column, cell_row) == "rock"
    document.undo()
    document.undo()

    block = document.block(GridRect(0, 0, 2, 2))
    assert block is not None
    stamped = document.stamp(8, 8, block)
    assert stamped
    document.undo()

    target = Path(tempfile.mkdtemp()) / "editor_roundtrip.json"
    saved = document.save(target)
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert payload["rows"], "la carte reecrite doit avoir des lignes"
    assert "player_spawn" in payload["legend"].values()
    saved.unlink()
    print(f"  editeur document -> {document.columns}x{document.rows}, "
          f"{len(palette.PALETTE)} elements de palette")


def check_editor_views(window: arcade.Window) -> None:
    """Le navigateur et la vue d'edition se dessinent, peignent et annulent."""
    from src.editor.browser import BrowserView
    from src.editor.document import EditorDocument
    from src.editor.edit_view import EditView, Tool

    browser = BrowserView()
    window.show_view(browser)
    browser.on_draw()
    browser.on_resize(window.width, window.height)

    document = EditorDocument.from_file("level_1_tuto.json")
    view = EditView(document)
    window.show_view(view)
    view.on_show_view()
    view.on_draw()
    view.kind = "rock"
    view.tool = Tool.BRUSH
    screen_x = view.canvas.viewport.center_x
    screen_y = view.canvas.viewport.center_y
    view.on_mouse_press(screen_x, screen_y, arcade.MOUSE_BUTTON_LEFT, 0)
    view.on_mouse_release(screen_x, screen_y, arcade.MOUSE_BUTTON_LEFT, 0)
    view.on_key_press(arcade.key.Z, arcade.key.MOD_CTRL)
    view.on_key_press(arcade.key.Z, arcade.key.MOD_CTRL | arcade.key.MOD_SHIFT)
    view.on_draw()
    print("  editeur vues -> navigateur et grille OK")


def main() -> int:
    print("Project Astral Platformer - smoke test")
    print("[1/10] chargement des cartes")
    check_levels()
    print("[2/10] progression et ameliorations")
    check_progression()
    print("[3/10] event manager")
    check_event_manager()
    print("[4/10] modele de l'editeur")
    check_editor_document()
    print("[5/10] IA ennemie")
    check_enemy_ai()

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
        print("[6/10] boucle de jeu")
        check_gameplay_loop(window)
        print("[7/10] defilement vertical de la camera")
        check_vertical_scroll(window)
        print("[8/10] solution du niveau tutoriel")
        check_tutorial_is_solvable(window)
        print("[9/10] menus")
        check_menus(window)
        print("[10/10] vues de l'editeur")
        check_editor_views(window)
    finally:
        window.close()
    print("OK : le squelette demarre et tourne.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
