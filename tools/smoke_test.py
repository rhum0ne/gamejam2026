"""Test de demarrage automatique, sans interaction humaine.

Il verifie que le squelette tourne vraiment : chargement des cartes, creation
de la fenetre, boucle de jeu, passage en mode fantome, retour au corps, logique
de progression. A lancer avant chaque commit et en CI :

    python tools/smoke_test.py

La fenetre est creee en mode invisible (`visible=False`) : aucune fenetre
n'apparait, mais le contexte OpenGL est bien reel, donc `on_draw` est teste.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arcade  # noqa: E402

import settings  # noqa: E402
from src.entities.bat import Bat, BatState  # noqa: E402
from src.entities.boss import Boss, BossShot, BossState  # noqa: E402
from src.entities.enemy import Enemy, EnemyState  # noqa: E402
from src.entities.item import ItemKind  # noqa: E402
from src.entities.particles import LaserBurst  # noqa: E402
from src.entities.player import Player  # noqa: E402
from src.entities.zombie import Zombie, ZombieState  # noqa: E402
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
            assert any(isinstance(enemy, Bat) for enemy in level.enemies), (
                f"{name} : chauve-souris manquante"
            )
            extra = f", {len(level.mechanisms)} plaque(s), {hanging} pique(s) plafond"
        print(f"  carte '{name}' -> {level.name}: {level.columns}x{level.rows} tuiles, "
              f"{len(level.walls)} murs, {len(level.items)} objets, {len(level.enemies)} ennemis{extra}")
        assert level.theme in settings.GROUND_THEMES, f"{name} : theme inconnu '{level.theme}'"
    check_invalid_activator()
    check_inverted_activator()
    check_gated_flamethrower()
    check_link_actions()
    check_spectral_button()
    check_ground_theme()
    check_sfx_files()
    check_hidden_wall()


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


def check_gated_flamethrower() -> None:
    """Une plaque peut eteindre un lance-flammes, ou le reveler si inversee."""
    data = {
        "name": "flame-gate",
        "tile_size": 32,
        "legend": {"#": "wall", "P": "player_spawn", "f": "flamethrower"},
        "rows": [
            "#####",
            "#P.f#",
            "#####",
        ],
        "activators": [
            {
                "x": 1,
                "y": 1,
                "width": 1,
                "activate": {"setBlock": [{"x": 3, "y": 1, "type": "void"}]},
            }
        ],
    }
    level = Level.from_dict(data)
    assert len(level.flamethrowers) == 1
    assert len(level.mechanisms) == 1
    thrower = level.flamethrowers[0]
    mechanism = level.mechanisms[0]
    assert mechanism.targets[0].sprite is thrower
    mechanism.set_pressed(True, ())
    assert thrower not in level.flamethrowers
    assert not thrower.is_lethal
    mechanism.set_pressed(False, ())
    assert thrower in level.flamethrowers

    inverted = {
        **data,
        "activators": [
            {
                "x": 1,
                "y": 1,
                "width": 1,
                "invert": True,
                "activate": {"setBlock": [{"x": 3, "y": 1, "type": "void"}]},
            }
        ],
    }
    shown = Level.from_dict(inverted)
    assert len(shown.flamethrowers) == 0, "inverse : le lance-flammes est cache au repos"
    shown.mechanisms[0].set_pressed(True, ())
    assert len(shown.flamethrowers) == 1, "inverse : le lance-flammes apparait a l'activation"
    print("  plaque + lance-flammes -> cache a l'activation, montre si inverse")


def check_link_actions() -> None:
    """Chaque cible a sa propre action : cacher, montrer, allumer."""
    data = {
        "name": "actions",
        "tile_size": 32,
        "legend": {"#": "wall", "P": "player_spawn", "f": "flamethrower"},
        "rows": [
            "#######",
            "#P##.f#",
            "#######",
        ],
        "activators": [
            {
                "x": 1,
                "y": 1,
                "width": 1,
                "activate": {
                    "setBlock": [
                        {"x": 2, "y": 1, "type": "void", "action": "hide"},
                        {"x": 3, "y": 1, "type": "void", "action": "show"},
                        {"x": 5, "y": 1, "type": "void", "action": "ignite"},
                    ]
                },
            }
        ],
        "flamethrowers": [{"x": 5, "y": 1, "interval": 8.0, "dir": "right"}],
    }
    level = Level.from_dict(data)
    mechanism = level.mechanisms[0]
    hide_tile, show_tile, ignite_tile = mechanism.targets
    thrower = ignite_tile.sprite
    assert hide_tile.action == settings.LINK_ACTION_HIDE
    assert show_tile.action == settings.LINK_ACTION_SHOW
    assert ignite_tile.action == settings.LINK_ACTION_IGNITE
    assert not hide_tile.hidden
    assert show_tile.hidden
    assert thrower in level.flamethrowers
    assert not thrower.commanded_on
    assert not thrower.is_lethal
    mechanism.set_pressed(True, ())
    assert hide_tile.hidden
    assert not show_tile.hidden
    assert thrower in level.flamethrowers
    assert thrower.commanded_on
    assert thrower.activator_driven
    thrower._age = 0.0
    thrower.update(thrower.interval * 0.9)
    assert thrower.intensity == 1.0
    assert thrower.is_lethal, "un lance-flammes d'activateur ignore son intervalle"
    mechanism.set_pressed(False, ())
    assert not hide_tile.hidden
    assert show_tile.hidden
    assert not thrower.commanded_on
    assert not thrower.is_lethal
    print("  actions par lien -> hide / show / ignite independants")


def check_spectral_button() -> None:
    """Bouton spectral : pas de poids, timer, invisible au corps."""
    data = {
        "name": "spectral",
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
                "x": 2,
                "y": 1,
                "width": 1,
                "kind": "spectral",
                "duration": 1.0,
                "activate": {
                    "setBlock": [{"x": 2, "y": 2, "type": "void", "action": "show"}]
                },
            }
        ],
    }
    level = Level.from_dict(data)
    assert len(level.spectral_buttons) == 1
    assert len(level.plates) == 0
    mechanism = level.mechanisms[0]
    assert mechanism.kind == settings.ACTIVATOR_KIND_SPECTRAL
    assert mechanism.duration == 1.0
    tile = mechanism.targets[0]
    assert tile.hidden, "show : cache au repos"
    mechanism.set_pressed(True, ())
    assert not tile.hidden
    mechanism.press(())
    assert mechanism.time_left == 1.0
    assert mechanism.pressed
    released = mechanism.tick(0.4, ())
    assert not released
    assert mechanism.pressed
    released = mechanism.tick(0.7, ())
    assert released
    assert not mechanism.pressed
    assert tile.hidden
    print("  bouton spectral -> visible seulement en fantome, duree 1s")


def check_ground_theme() -> None:
    """Le champ optionnel `theme` choisit la planche, ou ground par defaut."""
    from src.world.themes import next_theme, sheet_for, theme_ids

    data = {
        "name": "theme",
        "tile_size": settings.TILE_SIZE,
        "legend": {"#": "wall", "P": "player_spawn"},
        "rows": ["####", "#P.#", "####"],
    }
    default = Level.from_dict(data)
    assert default.theme == settings.GROUND_THEME_DEFAULT
    empty = Level.from_dict({**data, "theme": ""})
    assert empty.theme == settings.GROUND_THEME_DEFAULT
    sand = Level.from_dict({**data, "theme": "sand"})
    assert sand.theme == "sand"
    rock = Level.from_dict({**data, "theme": "ROCK"})
    assert rock.theme == "rock"
    try:
        Level.from_dict({**data, "theme": "lava"})
    except LevelFormatError as error:
        message = str(error)
        assert "theme inconnu" in message, message
    else:
        raise AssertionError("un theme inconnu aurait du etre refuse")
    try:
        Level.from_dict({**data, "theme": 1})
    except LevelFormatError as error:
        assert "theme" in str(error)
    else:
        raise AssertionError("un theme non chaine aurait du etre refuse")
    for theme_id in theme_ids():
        path = sheet_for(theme_id)
        assert path.is_file(), f"planche manquante pour '{theme_id}' : {path}"
    assert next_theme("ground") == "sand"
    assert next_theme("sand") == "rock"
    assert next_theme("rock") == "ground"
    ground_key = next(iter(default.walls)).texture.cache_name
    sand_key = next(iter(sand.walls)).texture.cache_name
    rock_key = next(iter(rock.walls)).texture.cache_name
    assert ground_key != sand_key, "sand doit lire une autre planche que ground"
    assert sand_key != rock_key, "rock doit lire une autre planche que sand"
    print(f"  theme terrain -> defaut {default.theme}, sand/rock distincts, cycle OK")


def check_sfx_files() -> None:
    """Les bruitages branches dans le jeu sont bien presents sur disque."""
    names = (
        settings.SOUND_ATTACK,
        settings.SOUND_LEVEL_WIN,
        settings.SOUND_SOUL_GET,
        settings.SOUND_CHECKPOINT,
        settings.SOUND_KEY_FOUND,
        settings.SOUND_MENU_CLICK,
        settings.SOUND_MENU_HOVER,
        settings.SOUND_MOB_HIT,
        settings.SOUND_GHOST_START,
        settings.SOUND_GHOST_END,
        settings.SOUND_DASH,
        settings.SOUND_JUMP,
        settings.SOUND_BOSS_FIRE,
        settings.SOUND_RESPAWN,
        settings.SOUND_FOOTSTEP,
    )
    for name in names:
        path = settings.SOUNDS_DIR / name
        assert path.is_file(), f"bruitage manquant : {path}"
    print(f"  bruitages -> {len(names)} fichiers")


def check_hidden_wall() -> None:
    """Bloc invisible : charge, masque, solide pour le vivant et le fantome."""
    data = {
        "name": "hidden",
        "tile_size": 32,
        "legend": {"#": "wall", "h": settings.TILE_KIND_HIDDEN, "P": "player_spawn"},
        "rows": [
            "#####",
            "#P.h#",
            "#####",
        ],
    }
    level = Level.from_dict(data)
    assert len(level.hidden_walls) == 1, "la fabrique hidden_wall doit poser un sprite"
    wall = level.hidden_walls[0]
    assert not wall.visible, "le bloc invisible ne doit pas se dessiner vivant"
    assert wall.alpha == 0
    assert level.hidden_walls in level.static_walls
    assert level.hidden_walls in level.ghost_walls
    assert level.spectral_walls not in level.ghost_walls
    print("  bloc invisible -> charge, masque, solide")


def check_progression() -> None:
    """XP + ames exponentiels ; les ameliorations sont choisies, pas automatiques."""
    progression = SoulProgression()
    assert progression.level == 1
    assert progression.essence == 0
    assert progression.ghost_stats.duration == settings.GHOST_DURATION
    assert progression.ghost_stats.speed == settings.GHOST_SPEED
    leveled_up = False
    for _ in range(3):
        leveled_up = progression.absorb_orb() or leveled_up
    assert progression.level == 2, "3 ames doivent suffire pour le niveau 2 (courbe exponentielle)"
    assert leveled_up, "absorb_orb doit signaler la montee de niveau"
    assert progression.essence == 3, "l'essence (monnaie) n'est jamais depensee toute seule"
    # Les stats du fantome ne bougent pas tant qu'aucune carte n'a ete choisie.
    assert progression.ghost_stats.duration == settings.GHOST_DURATION
    assert progression.ghost_stats.speed == settings.GHOST_SPEED

    first_cost = progression.upgrade_cost("duration")
    progression.apply_upgrade("duration")
    assert progression.ghost_stats.duration == settings.GHOST_DURATION + settings.GHOST_UPGRADE_DURATION_BONUS
    assert progression.essence == 3 - first_cost
    second_cost = progression.upgrade_cost("duration")
    assert second_cost > first_cost, "le prix d'une amelioration doit croitre a chaque achat"

    cards = progression.upgrade_cards()
    assert {card.kind for card in cards} == {"vision", "speed", "duration"}
    print(
        f"  progression -> niveau {progression.level}, {progression.essence} ame(s), "
        f"duree fantome {progression.ghost_stats.duration:.1f}s "
        f"(prochaine carte duree : {second_cost} ame(s))"
    )


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


def _player_at(x: float, y: float) -> Player:
    """Player positionne exactement a (x, y).

    `Player.__init__` appelle `_place_on_tile` (magnetisme au sol le plus
    proche) : sans cette reaffectation apres coup, les positions precises
    utilisees par `check_bat_ai` (cone d'attaque, etc.) seraient faussees.
    """
    player = Player(x, y)
    player.center_x, player.center_y = x, y
    return player


def check_bat_ai() -> None:
    """Sommeil/reveil, poursuite en vol libre, cone d'attaque (piquet vs charge), laisse, mort animee.

    Meme principe que `check_enemy_ai` : des `Bat`/`Player` isoles (pas de
    fenetre necessaire pour la logique, seul le dessin en demande une).
    """
    bat = Bat(300.0, 300.0)
    assert bat.state is BatState.SLEEP
    assert not bat.weighs_on_plates, "une chauve-souris volante ne doit pas peser sur une plaque"

    # Joueur hors de portee de reveil : reste endormie.
    player = _player_at(bat.center_x + settings.BAT_WAKE_RANGE + 40.0, bat.center_y)
    bat.update(FRAME, player=player, corpses=None)
    assert bat.state is BatState.SLEEP, "trop loin : la chauve-souris ne doit pas se reveiller"

    # A portee : se reveille, puis part en poursuite une fois l'animation finie.
    player.center_x = bat.center_x + settings.BAT_WAKE_RANGE - 10.0
    player.center_y = bat.center_y
    bat.update(FRAME, player=player, corpses=None)
    assert bat.state is BatState.WAKE, "a portee de reveil : doit se reveiller"
    for _ in range(200):
        bat.update(FRAME, player=player, corpses=None)
        if bat.state is not BatState.WAKE:
            break
    assert bat.state is BatState.CHASE, "le reveil doit se terminer et lancer la poursuite"

    # Poursuite : vole librement vers le joueur (pas de gravite, 2 axes).
    player.center_x, player.center_y = bat.center_x + 200.0, bat.center_y + 50.0
    for _ in range(10):
        bat.update(FRAME, player=player, corpses=None)
    assert bat.change_x > 0.0, "doit voler vers un joueur situe a l'est"
    assert bat.change_y > 0.0, "doit voler vers un joueur situe plus haut"

    # Cone d'attaque : le piquet se declenche aussi si le joueur est *presque*
    # en-dessous, pas seulement pile en-dessous (BAT_DIVE_CONE_ANGLE).
    straight_below = _player_at(bat.center_x, bat.center_y - settings.BAT_DIVE_MIN_DROP - 20.0)
    assert bat._pick_attack(straight_below) is bat._dive, "pile en-dessous : doit piquer"
    offset_below = _player_at(bat.center_x + 15.0, bat.center_y - settings.BAT_DIVE_MIN_DROP - 20.0)
    assert bat._pick_attack(offset_below) is bat._dive, (
        "presque en-dessous, dans le cone : doit aussi piquer"
    )
    outside_cone = _player_at(bat.center_x + 40.0, bat.center_y - 25.0)
    assert bat._pick_attack(outside_cone) is None, (
        "angle trop grand par rapport a la verticale (hors cone) et trop haut pour charger : pas d'attaque"
    )
    same_height = _player_at(bat.center_x + settings.BAT_ATTACK_RANGE - 5.0, bat.center_y)
    assert bat._pick_attack(same_height) is bat._lunge, "a peu pres a la meme hauteur : doit charger"

    # Piquet declenche par la boucle de jeu : ne tue que sur les frames actives.
    diver = Bat(300.0, 300.0)
    diver.state = BatState.CHASE
    prey = _player_at(diver.center_x, diver.center_y - settings.BAT_DIVE_MIN_DROP - 20.0)
    diver.update(FRAME, player=prey, corpses=None)
    assert diver.state is BatState.ATTACK and diver._animator.animation is diver._dive
    assert collisions.enemy_striking_player(prey, [diver]) is None, (
        "les premieres frames de l'attaque (armement) ne doivent pas tuer"
    )
    frames_to_hit = None
    for frame in range(120):
        diver.update(FRAME, player=prey, corpses=None)
        if collisions.enemy_striking_player(prey, [diver]) is diver:
            frames_to_hit = frame + 1
            break
    assert frames_to_hit is not None, "un joueur immobile pile sous la chauve-souris doit etre touche"
    for _ in range(120):
        diver.update(FRAME, player=prey, corpses=None)
        if diver.state is not BatState.ATTACK:
            break
    assert diver.state is BatState.CHASE, "l'attaque finie doit reprendre la poursuite (avec recharge)"

    # Regression : l'ATTAQUE doit vraiment rapprocher l'ancre du sprite du
    # joueur, pas seulement jouer l'animation de piquet/charge sur place
    # (bug corrige : la planche a elle seule un mouvement marque, mais sans
    # deplacer le sprite, l'attaque semblait foncer sur le joueur sans jamais
    # le toucher pour de vrai des qu'il n'etait pas deja tout pres).
    charger = Bat(300.0, 300.0)
    charger.state = BatState.CHASE
    far_prey = _player_at(charger.center_x + settings.BAT_ATTACK_RANGE - 5.0, charger.center_y)
    start_distance = math.dist((charger.center_x, charger.center_y), (far_prey.center_x, far_prey.center_y))
    charger.update(FRAME, player=far_prey, corpses=None)
    assert charger.state is BatState.ATTACK and charger._animator.animation is charger._lunge
    for _ in range(30):
        charger.update(FRAME, player=far_prey, corpses=None)
    end_distance = math.dist((charger.center_x, charger.center_y), (far_prey.center_x, far_prey.center_y))
    assert end_distance < start_distance - 10.0, (
        "l'ancre de la chauve-souris doit vraiment se rapprocher du joueur pendant l'attaque "
        f"(depart {start_distance:.0f}px, arrivee {end_distance:.0f}px)"
    )

    # Regression : l'elan d'attaque ne doit pas osciller ("picorement") une
    # fois arrive pres du joueur (bug corrige : couper la cible sans annuler
    # la vitesse acquise laissait l'elan porter l'ancre hors de la zone
    # d'arrivee, qui se rearmait alors la frame suivante -> aller-retour).
    pecker = Bat(300.0, 300.0)
    pecker.state = BatState.CHASE
    pecker_prey = _player_at(pecker.center_x, pecker.center_y - settings.BAT_DIVE_MIN_DROP - 20.0)
    pecker.update(FRAME, player=pecker_prey, corpses=None)
    assert pecker.state is BatState.ATTACK
    previous = (pecker.center_x, pecker.center_y)
    previous_delta = (0.0, 0.0)
    reversals = 0
    for _ in range(80):
        pecker.update(FRAME, player=pecker_prey, corpses=None)
        current = (pecker.center_x, pecker.center_y)
        delta = (current[0] - previous[0], current[1] - previous[1])
        if delta[0] * previous_delta[0] < -1e-6 or delta[1] * previous_delta[1] < -1e-6:
            reversals += 1
        previous = current
        if delta != (0.0, 0.0):
            previous_delta = delta
        if pecker.state is not BatState.ATTACK:
            break
    assert reversals == 0, (
        f"l'ancre ne doit pas faire d'aller-retour pendant l'attaque ({reversals} inversion(s) de sens)"
    )

    # Laisse : trop loin de son perchoir, la chauve-souris abandonne et rentre,
    # puis se rendort une fois posee dessus.
    homebound = Bat(300.0, 300.0)
    homebound.state = BatState.CHASE
    homebound.center_x = homebound._home_x + settings.BAT_LEASH_RANGE + 50.0
    homebound.center_y = homebound._home_y
    homebound.update(
        FRAME, player=_player_at(homebound.center_x, homebound.center_y), corpses=None
    )
    assert homebound.state is BatState.RETURN, "trop loin de son perchoir : doit abandonner et rentrer"
    for _ in range(400):
        homebound.update(FRAME, player=None, corpses=None)
        if homebound.state is BatState.SLEEP:
            break
    assert homebound.state is BatState.SLEEP, "de retour au perchoir : doit se rendormir"
    assert math.dist((homebound.center_x, homebound.center_y), (300.0, 300.0)) < 1.0, (
        "doit atterrir pile sur son perchoir d'origine"
    )

    # Regression : le joueur reste colle a portee de reveil pendant tout le
    # retour (typiquement juste apres une esquive) -> ne doit pas reprendre la
    # poursuite en boucle (BAT_LEASH_RANGE et BAT_WAKE_RANGE sont deux seuils
    # independants ; annuler RETURN des que le joueur est proche recreait un
    # aller-retour CHASE <-> RETURN a chaque frame).
    clingy = Bat(300.0, 300.0)
    clingy.state = BatState.CHASE
    clingy.center_x = clingy._home_x + settings.BAT_LEASH_RANGE + 50.0
    clingy.center_y = clingy._home_y
    close_player = _player_at(clingy.center_x + 20.0, clingy.center_y)
    clingy.update(FRAME, player=close_player, corpses=None)
    assert clingy.state is BatState.RETURN, "trop loin de son perchoir : doit rentrer meme joueur tout pres"
    for _ in range(400):
        close_player.center_x, close_player.center_y = clingy.center_x + 20.0, clingy.center_y
        clingy.update(FRAME, player=close_player, corpses=None)
        assert clingy.state is not BatState.CHASE, (
            "ne doit pas reprendre la poursuite avant d'etre rentree se reposer"
        )
        if clingy.state is BatState.SLEEP:
            break
    assert clingy.state is BatState.SLEEP, "doit finir par rentrer et se rendormir malgre le joueur colle"

    # Mort : bille bleue, etat DYING, un 2e coup pendant DYING est ignore, animation finie.
    victim = Bat(300.0, 300.0)
    orb = victim.take_damage()
    assert orb is not None, "take_damage doit renvoyer une bille bleue a la mort"
    assert victim.state is BatState.DYING and victim.is_dying
    assert victim.take_damage() is None, "une chauve-souris DYING ignore les coups suivants"
    for _ in range(120):
        victim.update(FRAME, player=None, corpses=None)
    assert victim._animator.finished, "l'animation de mort doit se terminer"

    print(f"  IA chauve-souris -> reveil/poursuite/laisse, piquet a {frames_to_hit} frames, "
          "cone d'attaque, charge, mort animee OK")


def _tile_walls(tiles: list[tuple[int, int]]) -> arcade.SpriteList:
    """Mini-monde de tuiles (colonne, ligne ; ligne 0 en bas) pour tester une IA au sol."""
    walls = arcade.SpriteList(use_spatial_hash=True)
    for column, row in tiles:
        tile = arcade.SpriteSolidColor(settings.TILE_SIZE, settings.TILE_SIZE, color=arcade.color.GRAY)
        tile.left = column * settings.TILE_SIZE
        tile.bottom = row * settings.TILE_SIZE
        walls.append(tile)
    return walls


def _run_until(zombie: Zombie, player: Player | None, states: set[ZombieState], limit: int) -> int | None:
    """Fait tourner le zombie jusqu'a l'un des `states` ; retourne le nombre de frames ecoulees."""
    for frame in range(limit):
        zombie.update(FRAME, player=player, corpses=None)
        if zombie.state in states:
            return frame + 1
    return None


def check_zombie_ai() -> None:
    """Vision en cone + ligne de vue, cri puis course, memoire/recherche, griffe, 2 PV, chute.

    Meme principe que `check_enemy_ai` : entites isolees. Les cas qui ont
    besoin de murs (ligne de vue, chute) construisent un mini-monde de tuiles.
    """
    tile = settings.TILE_SIZE

    # Vision : rien dans son dos (hors contact), le joueur devant declenche le cri.
    zombie = Zombie(300.0, 300.0)
    assert zombie.state is ZombieState.PATROL and zombie.facing == -1
    player = _player_at(zombie.center_x + 120.0, zombie.center_y)
    zombie.update(FRAME, player=player, corpses=None)
    assert zombie.state is ZombieState.PATROL, "joueur dans le dos : le zombie ne doit pas le voir"
    player.center_x = zombie.center_x - 150.0
    zombie.update(FRAME, player=player, corpses=None)
    assert zombie.state is ZombieState.ALERT, "joueur devant, a portee de vue : doit crier"
    assert zombie.change_x == 0.0, "le cri immobilise le zombie"

    # Cri -> course : annonce d'abord, puis plus rapide qu'en patrouille.
    frames_alert = _run_until(zombie, player, {ZombieState.CHASE}, 120)
    assert frames_alert is not None and frames_alert > 10, "le cri doit durer avant la course"
    for _ in range(40):
        zombie.update(FRAME, player=player, corpses=None)
    assert zombie.change_x < -settings.ZOMBIE_PATROL_SPEED, "en poursuite, doit courir vers le joueur"

    # Memoire puis recherche : joueur hors de vue, il ne renonce pas tout de suite.
    player.center_x = zombie.center_x + settings.ZOMBIE_SIGHT_RANGE + 200.0
    frames_to_search = _run_until(zombie, player, {ZombieState.SEARCH}, 400)
    assert frames_to_search is not None, "vue perdue : doit finir par chercher"
    assert frames_to_search >= int(settings.ZOMBIE_MEMORY_TIME / FRAME) - 2, (
        "doit d'abord poursuivre le dernier point vu pendant ZOMBIE_MEMORY_TIME"
    )
    assert _run_until(zombie, player, {ZombieState.PATROL}, 400) is not None, (
        "recherche infructueuse : doit reprendre sa patrouille"
    )

    # Un mur entre eux bloque la vue ; sans le mur, il voit le joueur.
    floor = [(column, 0) for column in range(20)]
    pillar = [(10, row) for row in range(1, 4)]
    walls = _tile_walls(floor + pillar)
    watcher = Zombie(13.5 * tile, tile + settings.ZOMBIE_HEIGHT / 2 + 2.0)
    watcher.bind_world([walls])
    hidden = _player_at(7.5 * tile, tile + settings.PLAYER_HEIGHT / 2)
    for _ in range(20):
        watcher.update(FRAME, player=hidden, corpses=None)
        assert watcher.state is ZombieState.PATROL, "un mur entre eux doit bloquer la vue"
    for sprite in [sprite for sprite in walls if sprite.bottom >= tile]:
        sprite.remove_from_sprite_lists()
    assert _run_until(watcher, hidden, {ZombieState.ALERT}, 30) is not None, (
        "mur retire : doit voir le joueur"
    )

    # Griffe : annoncee (pas de degat au premier contact), puis touche un joueur
    # immobile. Sur un vrai sol : a la distance de declenchement, c'est le bond
    # (ZOMBIE_ATTACK_RANGE > ZOMBIE_ATTACK_REACH) qui amene la griffe au contact.
    clawer = Zombie(15.5 * tile, tile + settings.ZOMBIE_HEIGHT / 2 + 2.0)
    clawer.bind_world([_tile_walls([(column, 0) for column in range(30)])])
    _run_until(clawer, None, set(), 5)
    prey = _player_at(clawer.center_x - settings.ZOMBIE_ATTACK_RANGE + 5.0, clawer.center_y)
    start_x = clawer.center_x
    assert _run_until(clawer, prey, {ZombieState.ATTACK}, 120) is not None, "a portee : doit attaquer"
    assert collisions.enemy_striking_player(prey, [clawer]) is None, "le debut de l'attaque ne doit pas tuer"
    frames_to_hit = None
    for frame in range(120):
        clawer.update(FRAME, player=prey, corpses=None)
        if collisions.enemy_striking_player(prey, [clawer]) is clawer:
            frames_to_hit = frame + 1
            break
    assert frames_to_hit is not None and frames_to_hit > 5, "la griffe doit toucher apres l'armement"
    assert clawer.center_x < start_x - 5.0, "l'attaque doit etre un bond vers le joueur"

    # 2 PV : le 1er coup sonne (et coupe l'attaque en cours), sans bille bleue.
    assert clawer.take_damage() is None, "1er coup : le zombie survit"
    assert clawer.state is ZombieState.HURT and not clawer.is_dying
    assert not clawer.strike_active, "un zombie sonne ne frappe plus"
    prey.center_x = clawer.center_x + settings.ZOMBIE_SIGHT_RANGE + 100.0  # dans son dos, hors de vue
    assert _run_until(clawer, prey, {ZombieState.CHASE}, 120) is not None, "doit se remettre du coup"
    assert clawer.facing == 1 and clawer._memory_timer > 0.0, (
        "enrage : doit se tourner vers le joueur meme sans le voir"
    )
    orb = clawer.take_damage()
    assert orb is not None and clawer.state is ZombieState.DYING, "2e coup : mort et bille bleue"
    assert clawer.take_damage() is None, "un zombie DYING ignore les coups suivants"
    for _ in range(120):
        clawer.update(FRAME, player=prey, corpses=None)
    assert clawer._animator.finished, "l'animation de mort doit se terminer"

    # Chute : se laisse tomber vers un joueur 3 tuiles plus bas...
    upper = [(column, 4) for column in range(10)]
    lower = [(column, 1) for column in range(25)]
    walls = _tile_walls(upper + lower)
    diver = Zombie(9.5 * tile, 5 * tile + settings.ZOMBIE_HEIGHT / 2 + 2.0)
    diver.facing = 1
    diver.bind_world([walls])
    below = _player_at(15.5 * tile, 2 * tile + settings.PLAYER_HEIGHT / 2)
    landed = False
    for _ in range(400):
        diver.update(FRAME, player=below, corpses=None)
        if diver.bottom < 3 * tile and diver._grounded:
            landed = True
            break
    assert landed, f"doit sauter de la plateforme vers le joueur (etat {diver.state.name}, bas={diver.bottom:.0f})"

    # ... mais pas dans un puits plus profond que ZOMBIE_MAX_DROP_TILES.
    deep = settings.ZOMBIE_MAX_DROP_TILES + 3
    walls = _tile_walls([(column, deep) for column in range(10)] + [(column, 0) for column in range(25)])
    cautious = Zombie(9.5 * tile, (deep + 1) * tile + settings.ZOMBIE_HEIGHT / 2 + 2.0)
    cautious.facing = 1
    cautious.bind_world([walls])
    _run_until(cautious, None, set(), 10)
    assert not cautious._may_drop(tile), "puits trop profond : ne doit pas s'y jeter"

    print(f"  IA zombie -> cone de vision, mur bloquant, cri {frames_alert} frames, memoire "
          f"{frames_to_search} frames, griffe a {frames_to_hit} frames, 2 PV, chute OK")


def check_boss_ai() -> None:
    """Le boss arme un projectile et un laser, puis meurt en plusieurs coups."""
    boss = Boss(400.0, 300.0)
    assert boss.state is BossState.PATROL
    player = _player_at(boss.center_x - 180.0, boss.center_y)
    attacked = False
    for _ in range(90):
        boss.update(FRAME, player=player, corpses=None)
        if boss.state in {BossState.SHOOT, BossState.LASER}:
            attacked = True
            break
    assert attacked, "le boss doit attaquer un joueur a portee"

    boss._attack_cooldown = 0.0
    boss._attack_index = 0
    boss._start_attack(player)
    assert boss.state is BossState.SHOOT, "cycle d'attaques : projectile d'abord"
    spawned = False
    for _ in range(int(2.5 / FRAME)):
        boss.update(FRAME, player=player, corpses=None)
        if boss.shots:
            spawned = True
            break
    assert spawned, "le lancer doit produire un projectile"
    shot = boss.shots[0]
    start_x = shot.center_x
    start_y = shot.center_y
    speed_start = math.hypot(shot.change_x, shot.change_y)
    boss.update(FRAME, player=player, corpses=None)
    assert shot.center_x < start_x, "le projectile doit partir vers le joueur"
    assert abs(shot.change_y) < abs(shot.change_x), "vise principalement le joueur a gauche"
    # Planche oriente gauche : vol vers la gauche = pas de rotation.
    shot_angle = shot.angle % 360.0
    assert shot_angle < 22.0 or shot_angle > 338.0, "le sprite projectile doit rester oriente a gauche"
    for _ in range(int(1.4 / FRAME)):
        if shot not in boss.shots:
            break
        shot.update(FRAME)
    speed_later = math.hypot(shot.change_x, shot.change_y)
    assert speed_later < speed_start * 0.75, "le projectile doit ralentir en vol"

    boss._clear_shots()
    player.center_y = boss.center_y + 90.0
    boss._spawn_shot(player, jitter_deg=0.0)
    aimed = boss.shots[0]
    assert aimed.change_y > 0.0, "le projectile doit viser le joueur en hauteur"
    assert aimed.change_x < 0.0, "le projectile doit rester oriente vers le joueur"
    aimed_angle = aimed.angle % 360.0
    assert 0.0 < aimed_angle < 90.0, "le sprite projectile doit tourner vers le joueur"

    wall = arcade.SpriteSolidColor(32, 64, (80, 80, 80))
    wall.center_x = start_x - 20.0
    wall.center_y = start_y
    walls = arcade.SpriteList()
    walls.append(wall)
    burst = LaserBurst()
    exploding = BossShot(
        start_x, start_y, wall.center_x, wall.center_y, [walls], burst=burst, jitter_deg=0.0
    )
    impact = arcade.SpriteList()
    impact.append(exploding)
    popped = False
    for _ in range(40):
        impact.update(FRAME)
        if burst.active:
            popped = True
            break
    assert popped, "le projectile doit exploser en particules contre un mur"
    player.center_y = boss.center_y

    boss._attack_cooldown = 0.0
    boss._attack_index = 1
    high = _player_at(boss.center_x - 140.0, boss.center_y + 90.0)
    boss._start_attack(high)
    assert boss.state is BossState.LASER
    assert boss._laser_dir_y > 0.2, "le rayon doit viser le joueur au-dessus des yeux"
    locked_x, locked_y = boss._laser_dir_x, boss._laser_dir_y
    high.center_x = boss.center_x + 160.0
    high.center_y = boss.center_y - 80.0
    boss._aim_laser(high, FRAME)
    turned = math.hypot(boss._laser_dir_x - locked_x, boss._laser_dir_y - locked_y)
    snapped = math.hypot(boss._laser_dir_x - 1.0, boss._laser_dir_y + 0.5)
    assert turned < 0.25, "le laser doit suivre avec une courbe, pas un snap"
    assert snapped > 0.8, "le laser ne doit pas rattraper la cible en une frame"
    boss._end_attack()

    boss._attack_cooldown = 0.0
    boss._attack_index = 1
    boss._start_attack(player)
    assert boss.state is BossState.LASER
    assert not boss.laser_active, "les premieres frames de Laser_sheet ne sont pas encore le rayon"
    lit = False
    for _ in range(90):
        boss.update(FRAME, player=player, corpses=None)
        if boss.laser_active:
            lit = True
            break
    assert lit, "le laser doit s'allumer pendant l'anim"
    origin_x, origin_y = boss._laser_origin()
    player.center_x = origin_x + boss._laser_dir_x * 90.0
    player.center_y = origin_y + boss._laser_dir_y * 90.0
    assert boss.laser_hits(player), "un joueur sur la ligne du laser doit etre touche"
    player.center_x = origin_x + boss._laser_dir_x * 90.0 - boss._laser_dir_y * 220.0
    player.center_y = origin_y + boss._laser_dir_y * 90.0 + boss._laser_dir_x * 220.0
    assert not boss.laser_hits(player), "hors du rayon, le laser ne doit pas toucher"
    linger = 0
    while boss.laser_active:
        linger += 1
        boss.update(FRAME, player=player, corpses=None)
        if linger > 400:
            break
    min_hold = int(
        settings.BOSS_LASER_LINGER_FRAMES
        * settings.ANIM_BOSS_BEAM_FRAME_TIME
        / settings.ANIM_SPEED
        / FRAME
    )
    assert linger >= min_hold, "la derniere frame du laser doit rester affichee"

    player.center_x = boss.center_x - 180.0
    player.center_y = boss.center_y
    boss._attack_cooldown = 0.0
    boss._attack_index = 2
    boss._start_attack(player)
    assert boss.state is BossState.SPIKES, "cycle d'attaques : vague de piques"
    assert boss._spike_wave.slot_count >= settings.BOSS_SPIKE_COUNT_MIN
    warning_frames = max(1, int(settings.BOSS_SPIKE_WARN_TIME / FRAME) - 2)
    for _ in range(warning_frames):
        boss.update(FRAME, player=player, corpses=None)
        assert not boss.spike_hits(player), "le warning ne doit pas etre mortel"
    for _ in range(int(0.25 / FRAME)):
        boss.update(FRAME, player=player, corpses=None)
        if any(getattr(sprite, "lethal", False) for sprite in boss._spike_wave.sprites):
            break
    lethal = next(
        (sprite for sprite in boss._spike_wave.sprites if getattr(sprite, "lethal", False)),
        None,
    )
    assert lethal is not None, "les piques doivent apparaitre apres le warning"
    player.center_x = lethal.center_x
    player.center_y = lethal.center_y
    assert boss.spike_hits(player), "une pique armee doit toucher le joueur"
    assert collisions.player_hits_boss_attack(player, [boss])

    orb = None
    for _ in range(settings.BOSS_HIT_POINTS):
        orb = boss.take_damage()
    assert orb is not None and boss.state is BossState.DYING
    print("  IA boss -> projectile, laser, piques, 6 PV OK")


def check_combat(window: arcade.Window) -> None:
    """Un clic gauche declenche une frappe frontale et vainc un ennemi."""
    view = PlayView(GameSession())
    window.show_view(view)
    advance(view, 2)

    player = view.player
    enemy = next(item for item in view.level.enemies if isinstance(item, Enemy))
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
        0.0,
        view.camera.world.viewport_height / 2,
        arcade.MOUSE_BUTTON_LEFT,
        0,
    )
    assert player.facing == 1, "le clic ne doit pas changer le cote du coup"
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
    assert view.ghost is not None
    assert not arcade.check_for_collision_with_list(view.ghost, view.level.walls), (
        "le fantome ne doit pas naitre coince dans un mur"
    )

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

    cadaver = view.level.corpses[0]
    assert not cadaver.is_remnant, "un cadavre non devore n'est pas un squelette"
    cadaver.feed(settings.CORPSE_EAT_TIME)
    view.on_update(FRAME)
    assert cadaver.is_remnant, "un cadavre devore doit laisser un squelette"
    assert len(view.level.corpses) == 0, "le squelette ne doit plus etre solide"
    assert len(view.level.remains) == 1, "le squelette doit rester en decor"
    advance(view, 30)
    assert len(view.level.remains) == 1 and view.level.remains[0].alpha == 255, (
        "le squelette doit rester indefiniment"
    )

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
    assert view.level.remains, "la dissipation doit laisser un squelette"

    view.held_keys.add(arcade.key.RIGHT)
    previous_x = view.player.center_x
    start_level = view.session.level_index
    for _ in range(3500):
        blocked = abs(view.player.center_x - previous_x) < 0.2
        previous_x = view.player.center_x
        wall_probe = (view.player.center_x + 48, view.player.center_y)
        floor_probe = (view.player.center_x + view.player.width / 2 + 28, view.player.bottom - 4)
        wall_ahead = bool(
            arcade.get_sprites_at_point(wall_probe, view.level.walls)
            or arcade.get_sprites_at_point(wall_probe, view.level.hidden_walls)
        )
        hole_ahead = not (
            arcade.get_sprites_at_point(floor_probe, view.level.walls)
            or arcade.get_sprites_at_point(floor_probe, view.level.spectral_walls)
            or arcade.get_sprites_at_point(floor_probe, view.level.hidden_walls)
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
    assert play._debug_enabled is False, "l'overlay debug doit etre masque au lancement"
    play.on_key_press(arcade.key.F3, 0)
    assert play._debug_enabled is True, "F3 doit afficher l'overlay"
    play.on_key_press(arcade.key.F3, 0)
    assert play._debug_enabled is False, "F3 doit pouvoir le recacher"
    play.on_resize(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
    print("  menus -> titre, victoire, pause et resize OK")


def check_editor_document() -> None:
    """Le modele d'edition charge une carte, peint, annule, refait, reecrit."""
    import json
    import tempfile

    from src.editor.activators import can_link_kind
    from src.editor import palette
    from src.editor.document import DocumentError, EditorDocument
    from src.editor.selection import GridRect
    from src.world.level import gameplay_kinds

    kinds = {item.kind for item in palette.PALETTE}
    for kind in gameplay_kinds():
        assert kind in kinds, f"la palette doit lister le gameplay '{kind}'"
    assert "wall" in kinds and "enemy" in kinds and "bat" in kinds and "zombie" in kinds and "boss" in kinds and "spike" in kinds
    assert can_link_kind("wall") and can_link_kind("spike") and can_link_kind("spectral_wall")
    assert can_link_kind("flamethrower") and can_link_kind(settings.TILE_KIND_HIDDEN)
    assert not can_link_kind("enemy") and not can_link_kind("torch")

    document = EditorDocument.from_file("level_1_tuto.json")
    assert document.columns > 0 and document.rows > 0
    assert document.theme == settings.GROUND_THEME_DEFAULT
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
    assert "theme" not in payload, "le theme par defaut ne s'ecrit pas"
    document.set_metadata(theme="sand")
    sand_payload = document.to_dict()
    assert sand_payload["theme"] == "sand"
    restored_theme = EditorDocument.from_dict(sand_payload)
    assert restored_theme.theme == "sand"
    document.set_metadata(theme=settings.GROUND_THEME_DEFAULT)
    assert "theme" not in document.to_dict()
    try:
        EditorDocument.from_dict({**payload, "theme": "lava"})
    except DocumentError as error:
        assert "theme inconnu" in str(error)
    else:
        raise AssertionError("l'editeur doit refuser un theme inconnu")
    assert len(payload.get("activators", [])) == 2
    first = payload["activators"][0]
    assert first["x"] == 13 and first["width"] == 4
    assert first["activate"]["setBlock"]
    saved.unlink()

    index = document.add_activator(5, 5, 3)
    assert document.activators[index].width == 3
    linked = document.toggle_target(index, 2, document.rows - 2)
    assert linked
    target = document.activators[index].target_at(2, document.rows - 2)
    assert target is not None
    assert target.action == settings.LINK_ACTION_HIDE
    cycled = document.cycle_target_action(index, 2, document.rows - 2)
    assert cycled == settings.LINK_ACTION_SHOW
    kind = document.toggle_activator_kind(index)
    assert kind == settings.ACTIVATOR_KIND_SPECTRAL
    duration = document.adjust_activator_duration(index, 1.5)
    assert duration == settings.SPECTRAL_BUTTON_DURATION + 1.5
    invert_path = Path(tempfile.mkdtemp()) / "activator_actions.json"
    invert_saved = document.save(invert_path)
    invert_payload = json.loads(invert_saved.read_text(encoding="utf-8"))
    inverted_entry = next(
        entry
        for entry in invert_payload["activators"]
        if entry["x"] == 5 and entry["y"] == 5
    )
    assert "invert" not in inverted_entry
    assert inverted_entry.get("kind") == settings.ACTIVATOR_KIND_SPECTRAL
    assert inverted_entry["activate"]["setBlock"][0]["action"] == settings.LINK_ACTION_SHOW
    reloaded_invert = EditorDocument.from_file(invert_saved)
    restored_plate = next(
        plate
        for plate in reloaded_invert.activators
        if plate.column == 5 and plate.row == 5
    )
    assert restored_plate.is_spectral
    assert restored_plate.targets[0].action == settings.LINK_ACTION_SHOW
    invert_saved.unlink()
    document.undo()
    document.undo()
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
    assert not tuned_fall.ghost_only
    ghost_fall = document.adjust_falling(*fall_cell, invert_ghost=True)
    assert ghost_fall is not None and ghost_fall.ghost_only
    fall_path = Path(tempfile.mkdtemp()) / "falling_roundtrip.json"
    fall_saved = document.save(fall_path)
    fall_payload = json.loads(fall_saved.read_text(encoding="utf-8"))
    assert settings.TILE_KIND_FALLING in fall_payload["legend"].values()
    fall_entries = fall_payload.get("falling_blocks", [])
    assert fall_entries, "la carte doit ecrire le champ falling_blocks"
    assert abs(fall_entries[0]["delay"] - ghost_fall.delay) < 1e-6
    assert abs(fall_entries[0]["respawn"] - ghost_fall.respawn) < 1e-6
    assert fall_entries[0].get("ghost_only") is True
    reloaded_fall = EditorDocument.from_file(fall_saved)
    restored_fall = reloaded_fall.falling_at(*fall_cell)
    assert restored_fall is not None
    assert abs(restored_fall.delay - ghost_fall.delay) < 1e-6
    assert abs(restored_fall.respawn - ghost_fall.respawn) < 1e-6
    assert restored_fall.ghost_only
    fall_saved.unlink()
    document.undo()
    assert document.falling_at(*fall_cell) is None
    spring_cell = (9, 9)
    document.paint((spring_cell,), settings.TILE_KIND_SPRING)
    placed_spring = document.spring_at(*spring_cell)
    assert placed_spring is not None, "peindre un ressort doit creer ses reglages"
    assert placed_spring.direction == "up"
    tuned_spring = document.adjust_spring(*spring_cell, rotate=True)
    assert tuned_spring is not None and tuned_spring.direction == "right"
    spring_path = Path(tempfile.mkdtemp()) / "spring_roundtrip.json"
    spring_saved = document.save(spring_path)
    spring_payload = json.loads(spring_saved.read_text(encoding="utf-8"))
    assert settings.TILE_KIND_SPRING in spring_payload["legend"].values()
    spring_entries = spring_payload.get("springs", [])
    assert spring_entries, "la carte doit ecrire le champ springs"
    assert spring_entries[0]["dir"] == "right"
    reloaded_spring = EditorDocument.from_file(spring_saved)
    restored_spring = reloaded_spring.spring_at(*spring_cell)
    assert restored_spring is not None and restored_spring.direction == "right"
    spring_saved.unlink()
    document.undo()
    assert document.spring_at(*spring_cell) is None
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
    assert abs(player.change_x) > settings.PLAYER_SPEED * 0.85, (
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

    ghost_data = {
        "name": "Chute fantome",
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
            "########",
        ],
        "falling_blocks": [
            {"x": 3, "y": 3, "delay": 0.05, "respawn": 0.2, "ghost_only": True},
        ],
    }
    ghost_level = Level.from_dict(ghost_data)
    ghost_block = ghost_level.falling_blocks[0]
    assert ghost_block.ghost_only
    assert not ghost_block.visible, "invisible pour le corps"
    assert ghost_block.alpha == 0
    ghost_player = Player(*ghost_level.player_spawn)
    ghost_player.bind_world(
        ghost_level.static_walls,
        platforms=[ghost_level.corpses, ghost_level.falling_blocks],
    )
    for _ in range(6):
        ghost_level.update(FRAME)
        ghost_player.update(FRAME)
        if ghost_block.supports(ghost_player):
            ghost_block.arm()
    assert ghost_block.state is FallingState.ARMED or ghost_block.state is FallingState.FALLING
    assert not ghost_block.visible, "reste invisible une fois arme"
    ghost_block.set_ghost_view(True)
    assert ghost_block.visible, "le fantome doit voir le bloc"
    assert ghost_block.alpha == settings.FALLING_BLOCK_GHOST_ALPHA
    ghost_block.set_ghost_view(False)
    assert not ghost_block.visible
    print("  bloc tombant fantome -> invisible au corps, solide, visible au fantome")


def check_spring(window: arcade.Window) -> None:
    """Ressort vertical : garde vx, relance ~7 tuiles. Horizontal : inverse vx."""
    from src.systems import collisions
    from src.world.level import Level

    vertical = {
        "name": "Ressort vertical",
        "tile_size": settings.TILE_SIZE,
        "legend": {
            ".": "vide",
            "#": "wall",
            "S": settings.TILE_KIND_SPRING,
            "P": "player_spawn",
        },
        "rows": [
            "##########",
            "#........#",
            "#........#",
            "#........#",
            "#........#",
            "#........#",
            "#........#",
            "#........#",
            "#........#",
            "#........#",
            "#........#",
            "#........#",
            "#..P.....#",
            "#........#",
            "#..S.....#",
            "##########",
        ],
        "springs": [{"x": 3, "y": 14, "dir": "up"}],
    }
    level = Level.from_dict(vertical)
    assert len(level.springs) == 1
    spring = level.springs[0]
    assert spring.direction == "up"
    player = Player(*level.player_spawn)
    player.bind_world(level.static_walls, platforms=[level.corpses])
    player.walk(0)
    launched = False
    peak_rise = 0.0
    vx_kept = settings.PLAYER_SPEED

    def step() -> None:
        nonlocal launched, peak_rise, vx_kept
        if not launched:
            player.change_x = 2.0
        player.update(FRAME)
        for pad in collisions.springs_launching_player(player, level.springs):
            vx_kept = player.change_x
            pad.launch(player)
            launched = True
        if launched and player.change_y > 0.0:
            peak_rise = max(peak_rise, player.bottom - spring.top)
        level.update(FRAME)

    for _ in range(180):
        step()
        if launched and player.change_y <= 0.0 and peak_rise > settings.TILE_SIZE:
            break
    assert launched, "le ressort vertical doit relancer le joueur"
    target = settings.SPRING_LAUNCH_TILES * settings.TILE_SIZE
    assert abs(peak_rise - target) < settings.TILE_SIZE * 1.5, (
        f"montee {peak_rise:.1f} px, vise {target:.1f} px (~7 tuiles)"
    )
    assert abs(player.change_x) > abs(vx_kept) * 0.85, (
        f"le ressort vertical doit garder vx, restant {player.change_x:.2f}"
    )
    print(
        f"  ressort vertical -> {peak_rise / settings.TILE_SIZE:.1f} tuiles, "
        f"vx {player.change_x:.2f}"
    )

    horizontal = {
        "name": "Ressort horizontal",
        "tile_size": settings.TILE_SIZE,
        "legend": {
            ".": "vide",
            "#": "wall",
            "S": settings.TILE_KIND_SPRING,
            "P": "player_spawn",
        },
        "rows": [
            "########",
            "#......#",
            "#P....S#",
            "########",
        ],
        "springs": [{"x": 6, "y": 2, "dir": "left"}],
    }
    side_level = Level.from_dict(horizontal)
    side = side_level.springs[0]
    assert side.direction == "left"
    bumper = Player(*side_level.player_spawn)
    bumper.bind_world(side_level.static_walls, platforms=[side_level.corpses])
    bumper.walk(1)
    bumper.change_x = settings.PLAYER_SPEED
    flipped = False
    for _ in range(40):
        bumper.update(FRAME)
        for pad in collisions.springs_launching_player(bumper, side_level.springs):
            before = bumper.change_x
            pad.launch(bumper)
            flipped = True
            assert bumper.change_x * before < 0.0 or bumper.change_x < 0.0
        side_level.update(FRAME)
        if flipped:
            break
    assert flipped, "le ressort horizontal doit inverser l'elan"
    assert bumper.change_x < 0.0, f"vx devrait aller a gauche, {bumper.change_x:.2f}"
    print(f"  ressort horizontal -> vx inversee ({bumper.change_x:.2f})")

    open_sky = {
        "name": "Dash ressort",
        "tile_size": settings.TILE_SIZE,
        "legend": {".": "vide", "#": "wall", "P": "player_spawn"},
        "rows": [
            "#" + "." * 28 + "#",
            "#" + "." * 28 + "#",
            "#" + "." * 28 + "#",
            "#" + "." * 28 + "#",
            "#" + "." * 28 + "#",
            "#" + "." * 28 + "#",
            "#" + "." * 28 + "#",
            "#" + "." * 28 + "#",
            "#" + "." * 28 + "#",
            "#" + "." * 28 + "#",
            "#" + "." * 13 + "P" + "." * 14 + "#",
            "#" + "#" * 28 + "#",
        ],
    }
    dash_level = Level.from_dict(open_sky)
    dasher = Player(*dash_level.player_spawn)
    dasher.bind_world(dash_level.static_walls, platforms=[dash_level.corpses])
    for _ in range(4):
        dasher.update(FRAME)
    dasher.walk(1)
    assert dasher.dash(), "le dash doit partir"
    dasher.launch_vertical(settings.SPRING_LAUNCH_SPEED)
    assert dasher._dash_jump, "un dash dans un ressort doit se porter comme un dash-saut"
    dash_frames = int(settings.PLAYER_DASH_DURATION / FRAME) + 8
    for _ in range(dash_frames):
        dasher.walk(0)
        dasher.update(FRAME)
    assert not dasher.is_dashing, "la fenetre de dash doit etre terminee"
    assert abs(dasher.change_x) >= settings.PLAYER_DASH_SPEED * 0.85, (
        f"le dash dans un ressort doit garder l'elan, vx={dasher.change_x:.2f}"
    )
    print(f"  dash ressort vertical -> vx {dasher.change_x:.2f} apres le dash")

    bumper_dash = Player(*dash_level.player_spawn)
    bumper_dash.bind_world(dash_level.static_walls, platforms=[dash_level.corpses])
    for _ in range(4):
        bumper_dash.update(FRAME)
    bumper_dash.jump()
    for _ in range(3):
        bumper_dash.update(FRAME)
    bumper_dash.walk(1)
    assert bumper_dash.dash(), "le dash doit partir"
    bumper_dash.reverse_horizontal(-1)
    assert bumper_dash._dash_jump
    assert bumper_dash.change_x < 0.0
    for _ in range(dash_frames):
        bumper_dash.walk(0)
        bumper_dash.update(FRAME)
    assert bumper_dash.change_x <= -settings.PLAYER_DASH_SPEED * 0.85, (
        f"le dash inverse par un ressort doit garder l'elan, vx={bumper_dash.change_x:.2f}"
    )
    print(f"  dash ressort horizontal -> vx {bumper_dash.change_x:.2f} apres le dash")


def check_editor_views(window: arcade.Window) -> None:
    """Le navigateur et la vue d'edition se dessinent, peignent et annulent."""
    from src.editor.browser import BrowserView
    from src.editor.document import EditorDocument
    from src.editor.edit_view import EditView, Tool
    from src.editor.panel import TAB_PLAQUES
    from src.world.themes import next_theme

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
    before_theme = view.document.theme
    view.on_key_press(arcade.key.F5, 0)
    assert view.document.theme == next_theme(before_theme)
    view.on_draw()
    view.on_key_press(arcade.key.Z, arcade.key.MOD_CTRL | arcade.key.MOD_SHIFT)
    sand_x, sand_y = view.panel.theme_chip_center("sand")
    view.on_mouse_press(sand_x, sand_y, arcade.MOUSE_BUTTON_LEFT, 0)
    assert view.document.theme == "sand", "clic theme du panneau"
    plaques_x, plaques_y = view.panel.tab_center(TAB_PLAQUES)
    view.on_mouse_press(plaques_x, plaques_y, arcade.MOUSE_BUTTON_LEFT, 0)
    assert view.tool is Tool.LINK and view.panel.tab == TAB_PLAQUES
    view._link_index = 0
    view.on_draw()
    help_x, help_y = view.panel.help_center()
    view.on_mouse_press(help_x, help_y, arcade.MOUSE_BUTTON_LEFT, 0)
    assert view.help.visible, "bouton Aide du panneau"
    view.on_draw()
    view.on_mouse_press(help_x, help_y, arcade.MOUSE_BUTTON_LEFT, 0)
    assert not view.help.visible
    print("  editeur vues -> navigateur, onglets, themes et aide OK")


def main() -> int:
    print("Project Astral Platformer - smoke test")
    print("[1/17] chargement des cartes")
    check_levels()
    print("[2/17] progression et ameliorations")
    check_progression()
    print("[3/17] event manager")
    check_event_manager()
    print("[4/17] modele de l'editeur")
    check_editor_document()
    print("[5/17] IA ennemie (squelette)")
    check_enemy_ai()
    print("[6/17] IA ennemie (chauve-souris)")
    check_bat_ai()
    print("[7/18] IA ennemie (zombie)")
    check_zombie_ai()
    print("[8/18] IA ennemie (boss)")
    check_boss_ai()

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
        print("[9/18] combat")
        check_combat(window)
        print("[10/18] boucle de jeu")
        check_gameplay_loop(window)
        print("[11/18] defilement vertical de la camera")
        check_vertical_scroll(window)
        print("[12/18] solution du niveau tutoriel")
        check_tutorial_is_solvable(window)
        print("[13/18] menus")
        check_menus(window)
        print("[14/18] vues de l'editeur")
        check_editor_views(window)
        print("[15/18] lance-flammes")
        check_flamethrower(window)
        print("[16/18] glace")
        check_ice_block(window)
        print("[17/18] dash contre un mur")
        check_dash_stops_on_wall(window)
        print("[18/18] blocs tombants")
        check_falling_block(window)
        print("[19/19] ressorts")
        check_spring(window)
    finally:
        window.close()
    print("OK : le squelette demarre et tourne.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
