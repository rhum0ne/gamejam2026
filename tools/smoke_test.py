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
from src.ui.menus import LevelErrorView, TitleView, VictoryView  # noqa: E402
from src.world.level import Level, LevelFormatError  # noqa: E402

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
    check_invalid_activator()
    check_inverted_activator()


def check_invalid_activator() -> None:
    """Une plaque qui pointe dans le vide doit lever un message explicite."""
    from src.world.level import LevelFormatError

    data = {
        "name": "test",
        "tile_size": 32,
        "legend": {"#": "wall", "P": "player_spawn"},
        "rows": ["####", "#P.#", "####"],
        "activators": [
            {
                "x": 1,
                "y": 1,
                "width": 1,
                "activate": {"setBlock": [{"x": 2, "y": 1, "type": "void"}]},
            }
        ],
    }
    try:
        Level.from_dict(data)
    except LevelFormatError as error:
        message = str(error)
        assert "activators[0]" in message, message
        assert "(2, 1)" in message, message
        assert "case vide" in message, message
        print(f"  plaque orpheline -> {message}")
        return
    raise AssertionError("une plaque sans bloc aurait du etre refusee")


def check_inverted_activator() -> None:
    """Une plaque `invert` montre les blocs a l'activation au lieu de les cacher."""
    from src.world.level import Level

    data = {
        "name": "inverse",
        "tile_size": 32,
        "legend": {"#": "wall", "P": "player_spawn"},
        "rows": [
            "#####",
            "#P..#",
            "#.#.#",
            "#####",
        ],
        "activators": [
            {
                "x": 1,
                "y": 1,
                "width": 1,
                "invert": True,
                "activate": {"setBlock": [{"x": 2, "y": 2, "type": "void"}]},
            }
        ],
    }
    level = Level.from_dict(data)
    assert len(level.mechanisms) == 1
    mechanism = level.mechanisms[0]
    assert mechanism.inverted
    assert mechanism.targets
    assert all(tile.hidden for tile in mechanism.targets), "les blocs inverses sont caches au repos"
    mechanism.set_pressed(True, ())
    assert all(not tile.hidden for tile in mechanism.targets), "l'activation doit montrer les blocs"
    mechanism.set_pressed(False, ())
    assert all(tile.hidden for tile in mechanism.targets), "le relachement doit recacher les blocs"
    print("  plaque inversee -> cachee au repos, visible a l'activation")


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


def check_combat(window: arcade.Window) -> None:
    """Un clic gauche declenche une frappe frontale et vainc un ennemi."""
    view = PlayView(GameSession())
    window.show_view(view)
    advance(view, 2)

    player = view.player
    enemy = view.level.enemies[0]
    player_start_x = player.center_x
    player_start_y = player.center_y
    enemy_start_y = enemy.center_y

    # Le contact vertical ne doit plus etre une attaque : seul le clic gauche
    # doit infliger des degats aux ennemis.
    enemy.state = EnemyState.PATROL
    player.center_x = enemy.center_x
    player.center_y = enemy.center_y + settings.ENEMY_HEIGHT
    player.change_y = -5.0
    view._resolve_player_collisions()
    assert enemy.state is EnemyState.PATROL, "sauter sur un ennemi ne doit plus le vaincre"
    assert enemy.hit_points == enemy.max_hit_points, "le saut ne doit pas infliger de degats"
    assert player.change_y == -5.0, "le saut sur un ennemi ne doit pas rebondir"

    player.facing = 1
    player.center_x = player_start_x
    player.center_y = player_start_y
    enemy.center_x = player.right + abs(enemy.width) / 2 + 6
    enemy.center_y = enemy_start_y
    player.change_y = 0.0

    view.on_mouse_press(
        view.camera.world.viewport_width / 2 + 100,
        view.camera.world.viewport_height / 2,
        arcade.MOUSE_BUTTON_LEFT,
        0,
    )
    advance(view, 5)

    assert enemy.state is EnemyState.DYING, "un clic gauche doit vaincre l'ennemi a portee"
    assert any(item.kind is ItemKind.SOUL_ORB for item in view.level.items), (
        "un ennemi vaincu doit laisser une bille bleue"
    )
    advance(view, 120)
    assert enemy not in view.level.enemies, "un ennemi vaincu doit finir par disparaitre"
    print("  combat -> clic gauche, ennemi vaincu, ame generee")


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
            # Un pilote scripte est plus lent qu'un joueur, surtout depuis que
            # le puits du tutoriel a gagne des etages : on les neutralise.
            view.ghost.time_left = settings.GHOST_DURATION
            for corpse_sprite in view.level.corpses:
                corpse_sprite.time_left = settings.CORPSE_LIFETIME
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
    # Le puits a des etages intermediaires : on grimpe d'abord dans la
    # gaine, sinon le vol diagonal se coince sous les planchers.
    waypoint_y = corpse.center_y + 3 * settings.TILE_SIZE
    assert fly_to(
        lambda: key_item.center_x,
        lambda: waypoint_y,
        lambda: abs(view.ghost.center_y - waypoint_y) < 12,
    ), "le fantome doit pouvoir remonter du puits"
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
    start_level = view.session.level_index
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
        if view.machine.state is GameState.VICTORY or view.session.level_index > start_level:
            break
        if view.machine.state is GameState.GHOST:
            break
    assert (
        view.machine.state is GameState.VICTORY or view.session.level_index > start_level
    ), (
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
    error_view = LevelErrorView(
        session,
        LevelFormatError(
            "activators[0] : setBlock void : aucun bloc a (17, 41) (case vide)"
        ),
    )
    window.show_view(error_view)
    advance(error_view, 2)
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
    assert "wall" in kinds and "enemy" in kinds and "spike" in kinds

    document = EditorDocument.from_file("level_1_tuto.json")
    assert document.columns > 0 and document.rows > 0
    assert document.counts().get("player_spawn", 0) >= 1
    assert len(document.activators) == 2
    assert document.activators[0].width == 4
    assert document.activators[0].targets

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
    document.fill_rect(rect, "wall")
    for cell_column, cell_row in rect.cells():
        assert document.cell(cell_column, cell_row) == "wall"
    document.replace_kind("wall", "bedrock", rect)
    for cell_column, cell_row in rect.cells():
        assert document.cell(cell_column, cell_row) == "bedrock"
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
    assert len(payload.get("activators", [])) == 2
    first = payload["activators"][0]
    assert first["x"] == 13 and first["width"] == 4
    assert first["activate"]["setBlock"]
    saved.unlink()

    index = document.add_activator(5, 5, 3)
    assert document.activators[index].width == 3
    linked = document.toggle_target(index, 2, document.rows - 2)
    assert linked
    assert not document.activators[index].inverted
    assert document.toggle_activator_invert(index)
    invert_path = Path(tempfile.mkdtemp()) / "activator_invert.json"
    invert_saved = document.save(invert_path)
    invert_payload = json.loads(invert_saved.read_text(encoding="utf-8"))
    inverted_entry = next(
        entry
        for entry in invert_payload["activators"]
        if entry["x"] == 5 and entry["y"] == 5
    )
    assert inverted_entry.get("invert") is True
    reloaded_invert = EditorDocument.from_file(invert_saved)
    restored_plate = next(
        plate
        for plate in reloaded_invert.activators
        if plate.column == 5 and plate.row == 5
    )
    assert restored_plate.inverted
    invert_saved.unlink()
    document.undo()
    document.undo()
    document.undo()
    assert len(document.activators) == 2

    flame_cell = (6, 6)
    document.paint((flame_cell,), "flamethrower")
    placed = document.flame_at(*flame_cell)
    assert placed is not None, "peindre un lance-flammes doit creer ses reglages"
    tuned = document.adjust_flame(*flame_cell, range_delta=2, interval_delta=0.4, rotate=True)
    assert tuned is not None
    assert tuned.range_tiles == placed.range_tiles + 2
    assert tuned.direction == "down"
    flame_path = Path(tempfile.mkdtemp()) / "flamethrower_roundtrip.json"
    flame_saved = document.save(flame_path)
    flame_payload = json.loads(flame_saved.read_text(encoding="utf-8"))
    entries = flame_payload.get("flamethrowers", [])
    assert entries, "la carte doit ecrire le champ flamethrowers"
    assert entries[0]["range"] == tuned.range_tiles
    assert entries[0]["dir"] == "down"
    reloaded = EditorDocument.from_file(flame_saved)
    restored = reloaded.flame_at(*flame_cell)
    assert restored is not None and restored.range_tiles == tuned.range_tiles
    assert restored.direction == "down"
    flame_saved.unlink()
    document.undo()
    assert document.flame_at(*flame_cell) is None
    ice_cell = (7, 7)
    document.paint((ice_cell,), settings.TILE_KIND_ICE)
    assert document.cell(*ice_cell) == settings.TILE_KIND_ICE
    ice_saved = document.save(Path(tempfile.mkdtemp()) / "ice_roundtrip.json")
    ice_payload = json.loads(ice_saved.read_text(encoding="utf-8"))
    assert settings.TILE_KIND_ICE in ice_payload["legend"].values()
    ice_saved.unlink()
    document.undo()
    fall_cell = (8, 8)
    document.paint((fall_cell,), settings.TILE_KIND_FALLING)
    placed_fall = document.falling_at(*fall_cell)
    assert placed_fall is not None, "peindre un bloc tombant doit creer ses reglages"
    tuned_fall = document.adjust_falling(
        *fall_cell,
        delay_delta=0.15,
        respawn_delta=0.6,
    )
    assert tuned_fall is not None
    assert abs(tuned_fall.delay - (placed_fall.delay + 0.15)) < 1e-6
    assert abs(tuned_fall.respawn - (placed_fall.respawn + 0.6)) < 1e-6
    fall_path = Path(tempfile.mkdtemp()) / "falling_roundtrip.json"
    fall_saved = document.save(fall_path)
    fall_payload = json.loads(fall_saved.read_text(encoding="utf-8"))
    assert settings.TILE_KIND_FALLING in fall_payload["legend"].values()
    fall_entries = fall_payload.get("falling_blocks", [])
    assert fall_entries, "la carte doit ecrire le champ falling_blocks"
    assert abs(fall_entries[0]["delay"] - tuned_fall.delay) < 1e-6
    assert abs(fall_entries[0]["respawn"] - tuned_fall.respawn) < 1e-6
    reloaded_fall = EditorDocument.from_file(fall_saved)
    restored_fall = reloaded_fall.falling_at(*fall_cell)
    assert restored_fall is not None
    assert abs(restored_fall.delay - tuned_fall.delay) < 1e-6
    assert abs(restored_fall.respawn - tuned_fall.respawn) < 1e-6
    fall_saved.unlink()
    document.undo()
    assert document.falling_at(*fall_cell) is None
    print(f"  editeur document -> {document.columns}x{document.rows}, "
          f"{len(palette.PALETTE)} elements de palette")


def check_flamethrower(window: arcade.Window) -> None:
    """Le jet shader se dessine, tue le corps et les ennemis, et se configure."""
    from src.world.flamethrower import Flamethrower
    from src.world.level import Level

    data = {
        "name": "Lance",
        "tile_size": settings.TILE_SIZE,
        "legend": {".": "vide", "#": "rock", "f": "flamethrower", "P": "player_spawn"},
        "rows": [
            "######",
            "#P...#",
            "#f...#",
            "######",
        ],
        "flamethrowers": [
            {"x": 1, "y": 2, "range": 3, "interval": 0.0, "facing": 1},
        ],
    }
    level = Level.from_dict(data)
    assert len(level.flamethrowers) == 1
    thrower = level.flamethrowers[0]
    thrower.update(0.0)
    assert thrower.is_lethal, "intervalle 0 = jet permanent"
    player = Player(*level.player_spawn)
    player.center_x, player.center_y = thrower.flame_midpoint()
    assert collisions.player_hits_flame(player, level.flamethrowers)
    enemy = Enemy(*thrower.flame_midpoint())
    level.enemies.append(enemy)
    burned = collisions.enemies_hit_by_flame(level.enemies, level.flamethrowers)
    assert enemy in burned, "le jet doit tuer les ennemis"
    thrower.draw_flame()
    assert thrower.direction == "right"

    down = Flamethrower(200.0, 200.0, range_tiles=3, interval=0.0, direction="down")
    down.update(0.0)
    left, right, bottom, top = down.flame_bounds()
    assert top - bottom >= down.flame_length * 0.99
    assert right - left <= settings.FLAMETHROWER_HEIGHT + 1.0
    assert down.flame_midpoint()[1] < down.center_y
    assert down.nozzle()[1] < down.center_y
    assert top <= down.center_y + 1.0
    down.draw_flame()
    print(
        f"  lance-flammes -> portee {thrower.range_tiles} tuiles, "
        f"jet lethal, 4 axes, shader OK"
    )


def check_ice_block(window: arcade.Window) -> None:
    """Le bloc `ice_block` est solide et conserve l'elan du corps au sol."""
    from src.world.level import Level

    data = {
        "name": "Glace",
        "tile_size": settings.TILE_SIZE,
        "legend": {
            ".": "vide",
            "#": "rock",
            "~": settings.TILE_KIND_ICE,
            "P": "player_spawn",
        },
        "rows": [
            "############",
            "#..........#",
            "#P.........#",
            "#~~~~~~~~~~#",
            "############",
        ],
    }
    level = Level.from_dict(data)
    ices = [wall for wall in level.walls if getattr(wall, "slippery", False)]
    assert len(ices) == 10, f"attendu 10 blocs de glace, obtenu {len(ices)}"
    player = Player(*level.player_spawn)
    player.bind_world(level.static_walls, platforms=[level.corpses])
    player.walk(0)
    for _ in range(4):
        player.update(FRAME)
    assert player._standing_on_ice(), "le joueur doit reposer sur la glace"
    player.change_x = settings.PLAYER_SPEED
    for _ in range(24):
        player.update(FRAME)
    assert abs(player.change_x) > settings.PLAYER_SPEED * 0.45, (
        f"la glace doit conserver l'elan, vitesse restante {player.change_x:.2f}"
    )
    print(f"  glace -> {len(ices)} blocs, elan conserve ({player.change_x:.2f} px/frame)")


def check_dash_stops_on_wall(window: arcade.Window) -> None:
    """Un dash dans un mur coupe l'elan, au sol comme en l'air."""
    from src.world.level import Level

    data = {
        "name": "Dash mur",
        "tile_size": settings.TILE_SIZE,
        "legend": {".": "vide", "#": "wall", "P": "player_spawn"},
        "rows": [
            "#####",
            "#...#",
            "#...#",
            "#P..#",
            "#####",
        ],
    }
    level = Level.from_dict(data)

    def remaining_speed(*, airborne: bool) -> float:
        player = Player(*level.player_spawn)
        player.bind_world(level.static_walls, platforms=[level.corpses])
        for _ in range(6):
            player.update(FRAME)
        if airborne:
            player.center_y += settings.TILE_SIZE * 2
            player.change_y = 0.0
            player._was_on_ground = False
            player._time_off_ground = 1.0
        player.walk(1)
        assert player.dash(), "le dash doit partir"
        for _ in range(20):
            player.update(FRAME)
            if not player.is_dashing:
                player.walk(0)
        player.walk(0)
        player.update(FRAME)
        return player.change_x

    ground_vx = remaining_speed(airborne=False)
    air_vx = remaining_speed(airborne=True)
    assert abs(ground_vx) < 0.2, f"dash au sol contre un mur, vx={ground_vx:.2f}"
    assert abs(air_vx) < 0.2, f"dash aerien contre un mur, vx={air_vx:.2f}"
    print(f"  dash mur -> vx sol {ground_vx:.2f}, air {air_vx:.2f}")


def check_falling_block(window: arcade.Window) -> None:
    """Le bloc tombant s'effondre avec le joueur, traverse le terrain, puis respawn."""
    from src.world.falling_block import FallingState
    from src.world.level import Level

    data = {
        "name": "Chute",
        "tile_size": settings.TILE_SIZE,
        "legend": {
            ".": "vide",
            "#": "wall",
            "F": settings.TILE_KIND_FALLING,
            "P": "player_spawn",
        },
        "rows": [
            "########",
            "#......#",
            "#..P...#",
            "#..F...#",
            "#......#",
            "#..#...#",
            "#......#",
            "########",
        ],
        "falling_blocks": [
            {"x": 3, "y": 3, "delay": 0.05, "respawn": 0.2},
        ],
    }
    level = Level.from_dict(data)
    assert len(level.falling_blocks) == 1
    block = level.falling_blocks[0]
    assert abs(block.delay - 0.05) < 1e-6
    assert abs(block.respawn - 0.2) < 1e-6
    home_y = block.home_y
    wall_below = min(level.walls, key=lambda wall: abs(wall.center_x - block.center_x) + abs(wall.center_y - (home_y - settings.TILE_SIZE * 2)))
    player = Player(*level.player_spawn)
    player.bind_world(
        level.static_walls,
        platforms=[level.corpses, level.falling_blocks],
    )

    def step() -> None:
        level.update(FRAME)
        for falling in level.falling_blocks:
            if falling.just_respawned:
                falling.just_respawned = False
                falling.eject_upward(player)
        player.update(FRAME)
        for falling in level.falling_blocks:
            if falling.supports(player):
                falling.arm()
            falling.stick_rider(player)

    for _ in range(4):
        step()
    assert block.state is FallingState.ARMED or block.state is FallingState.FALLING
    for _ in range(12):
        step()
        if block.state is FallingState.FALLING:
            break
    assert block.state is FallingState.FALLING, "le bloc doit tomber apres le delay"
    y_before = block.center_y
    player_before = player.center_y
    for _ in range(8):
        step()
    assert block.center_y < y_before, "le bloc doit descendre"
    assert player.center_y < player_before, "le joueur doit tomber avec le bloc"
    while block.state is FallingState.FALLING and block.center_y > wall_below.center_y:
        step()
        assert block.center_y > -settings.TILE_SIZE * 4, "le bloc devrait deja avoir traverse le mur"
    assert block.state is FallingState.FALLING, "le bloc ne doit pas s'arreter sur un mur"
    assert block.center_y < wall_below.center_y, "le bloc traverse le terrain"

    while block.state is FallingState.FALLING:
        step()
        assert block.center_y > -settings.TILE_SIZE * 12
    assert block.state is FallingState.GONE
    waited = 0
    while block.state is FallingState.GONE:
        player.center_x = block.home_x
        player.center_y = block.home_y
        player.change_x = 0.0
        player.change_y = 0.0
        step()
        waited += 1
        assert waited < 60, "le bloc devrait respawn"
    assert block.state in (FallingState.IDLE, FallingState.ARMED)
    assert player.bottom >= block.top - 1.0, "le respawn doit pousser le joueur vers le haut"
    print(
        f"  bloc tombant -> delay {block.delay:.2f}s, chute a travers le terrain, "
        f"respawn ejecte"
    )


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
    view.kind = "wall"
    view.tool = Tool.BRUSH
    screen_x = view.canvas.viewport.center_x
    screen_y = view.canvas.viewport.center_y
    view.on_mouse_press(screen_x, screen_y, arcade.MOUSE_BUTTON_LEFT, 0)
    view.on_mouse_release(screen_x, screen_y, arcade.MOUSE_BUTTON_LEFT, 0)
    view.on_key_press(arcade.key.Z, arcade.key.MOD_CTRL)
    view.on_key_press(arcade.key.Z, arcade.key.MOD_CTRL | arcade.key.MOD_SHIFT)
    view.tool = Tool.LINK
    view._link_index = 0
    view.on_draw()
    print("  editeur vues -> navigateur et grille OK")


def main() -> int:
    print("Project Astral Platformer - smoke test")
    print("[1/11] chargement des cartes")
    check_levels()
    print("[2/11] progression et ameliorations")
    check_progression()
    print("[3/11] event manager")
    check_event_manager()
    print("[4/11] modele de l'editeur")
    check_editor_document()
    print("[5/11] IA ennemie")
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
        print("[6/11] combat")
        check_combat(window)
        print("[7/11] boucle de jeu")
        check_gameplay_loop(window)
        print("[8/11] defilement vertical de la camera")
        check_vertical_scroll(window)
        print("[9/11] solution du niveau tutoriel")
        check_tutorial_is_solvable(window)
        print("[10/11] menus")
        check_menus(window)
        print("[11/11] vues de l'editeur")
        check_editor_views(window)
        print("[11/11] lance-flammes")
        check_flamethrower(window)
        print("[12/12] glace")
        check_ice_block(window)
        print("[13/13] dash contre un mur")
        check_dash_stops_on_wall(window)
        print("[14/14] blocs tombants")
        check_falling_block(window)
    finally:
        window.close()
    print("OK : le squelette demarre et tourne.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
