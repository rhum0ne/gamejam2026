"""Etats de jeu et vue de jeu principale.

Deux choses vivent ici :

1. `GameState` / `GameStateMachine` : l'automate qui autorise (ou refuse) les
   transitions Menu -> Niveau -> Mort -> Mode Fantome -> Victoire.
2. `PlayView` : la vue Arcade qui fait tourner un niveau. Elle orchestre les
   entites, la camera, le HUD et applique les consequences des collisions
   detectees par `src.systems.collisions`.

La `GameSession` porte tout ce qui doit survivre au changement de vue ou de
niveau (essence d'ame, paliers du fantome, niveau courant, nombre de morts).

Note sur les imports : `menus.py` importe `PlayView` et `PlayView` doit pouvoir
afficher les menus. Les imports de `src.ui.menus` sont donc faits *dans* les
methodes, pour eviter un import circulaire.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto

import arcade

import settings
from src.entities.corpse import Corpse
from src.entities.ghost import Ghost
from src.entities.item import ItemKind
from src.entities.player import Player
from src.systems import collisions
from src.systems.play_events import bind_play_view, emit_ghost_end, emit_player_death, emit_player_win
from src.systems.upgrades import SoulProgression
from src.ui.debug import DebugOverlay, DebugSnapshot
from src.ui.display import handle_display_key
from src.ui.hud import Hud, HudData
from src.world.atmosphere import ForegroundAtmosphere
from src.world.camera import CameraRig
from src.world.fog import GhostFog
from src.world.level import Level


class GameState(Enum):
    """Etats possibles de la partie."""

    MENU = auto()
    PLAYING = auto()
    GHOST = auto()
    RESPAWNING = auto()
    VICTORY = auto()
    GAME_OVER = auto()


_TRANSITIONS: dict[GameState, frozenset[GameState]] = {
    GameState.MENU: frozenset({GameState.PLAYING}),
    GameState.PLAYING: frozenset(
        {GameState.GHOST, GameState.VICTORY, GameState.GAME_OVER, GameState.MENU}
    ),
    GameState.GHOST: frozenset({GameState.RESPAWNING, GameState.GAME_OVER, GameState.MENU}),
    GameState.RESPAWNING: frozenset({GameState.PLAYING, GameState.MENU}),
    GameState.VICTORY: frozenset({GameState.PLAYING, GameState.MENU}),
    GameState.GAME_OVER: frozenset({GameState.PLAYING, GameState.MENU}),
}

STATE_LABELS: dict[GameState, str] = {
    GameState.MENU: "Menu",
    GameState.PLAYING: "Corps physique",
    GameState.GHOST: "Projection astrale",
    GameState.RESPAWNING: "Retour au corps...",
    GameState.VICTORY: "Niveau termine",
    GameState.GAME_OVER: "Game Over",
}


class StateTransitionError(RuntimeError):
    """Transition d'etat interdite par `_TRANSITIONS`."""


class GameStateMachine:
    """Automate des etats de jeu, avec transitions explicitement autorisees."""

    def __init__(self, initial: GameState = GameState.MENU) -> None:
        self._state = initial
        self.history: list[GameState] = [initial]

    @property
    def state(self) -> GameState:
        return self._state

    def can(self, target: GameState) -> bool:
        return target in _TRANSITIONS[self._state]

    def to(self, target: GameState) -> None:
        """Change d'etat, ou leve `StateTransitionError` si c'est interdit."""
        if not isinstance(target, GameState):
            raise TypeError("target doit etre un GameState")
        if not self.can(target):
            raise StateTransitionError(f"transition interdite : {self._state.name} -> {target.name}")
        self._state = target
        self.history.append(target)

    def try_to(self, target: GameState) -> bool:
        """Variante tolerante de `to` : retourne False au lieu de lever."""
        if not self.can(target):
            return False
        self.to(target)
        return True


@dataclass(slots=True)
class GameSession:
    """Donnees de partie partagees entre toutes les vues."""

    progression: SoulProgression = field(default_factory=SoulProgression)
    level_index: int = 0
    deaths: int = 0
    knows_esprit: bool = False

    @property
    def level_file(self) -> str:
        return settings.LEVEL_SEQUENCE[self.level_index]

    @property
    def is_last_level(self) -> bool:
        return self.level_index >= len(settings.LEVEL_SEQUENCE) - 1

    def advance_level(self) -> bool:
        """Passe au niveau suivant. Retourne False si l'aventure est terminee."""
        if self.is_last_level:
            return False
        self.level_index += 1
        return True

    def restart(self) -> None:
        """Remet la session a zero (nouvelle partie depuis le menu titre)."""
        self.progression = SoulProgression()
        self.level_index = 0
        self.deaths = 0
        self.knows_esprit = False


# --------------------------------------------------------------------------- #
# Touches
# --------------------------------------------------------------------------- #

_LEFT_KEYS = frozenset({arcade.key.LEFT, arcade.key.A, arcade.key.Q})
_RIGHT_KEYS = frozenset({arcade.key.RIGHT, arcade.key.D})
_UP_KEYS = frozenset({arcade.key.UP, arcade.key.W, arcade.key.Z})
_DOWN_KEYS = frozenset({arcade.key.DOWN, arcade.key.S})
_JUMP_KEYS = frozenset({arcade.key.SPACE}) | _UP_KEYS
_PROJECT_KEY = arcade.key.F
_RETURN_KEY = arcade.key.R
_DASH_KEYS = frozenset({arcade.key.LSHIFT, arcade.key.RSHIFT})


class PlayView(arcade.View):
    """Vue d'un niveau : joue la boucle corps physique / fantome / cadavre."""

    def __init__(self, session: GameSession | None = None) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session if session is not None else GameSession()
        self.machine = GameStateMachine(GameState.MENU)
        self.camera = CameraRig()
        self.fog = GhostFog()
        self.atmosphere = ForegroundAtmosphere()
        self.hud = Hud(settings.WORLD_VIEW_WIDTH, settings.WORLD_VIEW_HEIGHT)
        self.debug = DebugOverlay()
        self._debug_enabled = settings.DEBUG_OVERLAY
        self.level: Level
        self.player: Player
        self.ghost: Ghost | None = None
        self.anchor_corpse: Corpse | None = None
        self.held_keys: set[int] = set()
        self._respawn_timer = 0.0
        self._delivered_items: list[ItemKind] = []
        bind_play_view(self)
        self._fps = 0.0
        self._last_draw_time = 0.0
        self.setup()

    def on_show_view(self) -> None:
        self.camera.on_resize(self.window.width, self.window.height)

    # ------------------------------------------------------------------ #
    # Mise en place
    # ------------------------------------------------------------------ #

    def setup(self) -> None:
        """(Re)charge le niveau courant de la session et remet les entites a zero."""
        self.level = Level.from_file(self.session.level_file)
        self.player = Player(*self.level.player_spawn)
        self.player.respawn_point = self.level.checkpoint_spawn
        for checkpoint in self.level.checkpoints:
            if (checkpoint.center_x, checkpoint.center_y) == self.level.checkpoint_spawn:
                checkpoint.activate()
        self.player.bind_world(self.level.static_walls, platforms=[self.level.corpses])
        for enemy in self.level.enemies:
            enemy.bind_world(self._static_platforms())
        self.camera.set_bounds(self.level.width, self.level.height)
        self._enemy_spawns = [(enemy, enemy.center_x, enemy.center_y) for enemy in self.level.enemies]
        self.camera.snap_to(self.player)
        self.ghost = None
        self.anchor_corpse = None
        self.held_keys.clear()
        self._respawn_timer = 0.0
        self._delivered_items.clear()
        self.machine = GameStateMachine(GameState.MENU)
        self.machine.to(GameState.PLAYING)

    def _static_platforms(self) -> list[arcade.SpriteList]:
        """Plateformes solides hors cadavres (un cadavre ne doit pas se bloquer lui-meme)."""
        return [self.level.walls, self.level.spectral_walls]

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #

    def on_draw(self) -> None:
        self._sample_fps()
        self.camera.begin_frame()
        self.camera.use_world()
        self.level.draw(self.camera.visible_rect())
        if self.player.alive:
            self.player.draw_fx()
            arcade.draw_sprite(self.player)
        if self.ghost is not None:
            if self.machine.state is GameState.GHOST:
                self._draw_ghost_layer(self.ghost)
            elif self.ghost.vanishing:
                arcade.draw_sprite(self.ghost)
        self.atmosphere.draw(self.camera.world)
        if settings.DEBUG_SHOW_HITBOXES:
            self._draw_hitboxes()
        self.camera.use_ui()
        self.hud.draw(self._hud_data())
        if self._debug_enabled:
            self.debug.draw(self._debug_snapshot())
        self.camera.present()

    def _draw_hitboxes(self) -> None:
        color = settings.COLOR_DEBUG_HITBOX
        view_rect = self.camera.visible_rect()
        self.level.draw_static_hit_boxes(color, view_rect)
        self.level.enemies.draw_hit_boxes(color)
        self.level.corpses.draw_hit_boxes(color)
        if self.player.alive:
            self.player.draw_hit_box(color)
        if self.ghost is not None:
            self.ghost.draw_hit_box(color)

    def _draw_ghost_layer(self, ghost: Ghost) -> None:
        """Voile radial, fleche vers le corps, et fantome."""
        for wall in self.level.spectral_walls:
            wall.set_revealed(ghost.reveals(wall))
            if wall.revealed:
                arcade.draw_sprite(wall)
        for item in self.level.items:
            if ghost.reveals(item):
                item.draw_fx()
                arcade.draw_sprite(item)
        for enemy in self.level.enemies:
            if ghost.reveals(enemy):
                arcade.draw_sprite(enemy)
        self.fog.draw(ghost, self.camera.world)
        ghost.draw_fx()
        arcade.draw_sprite(ghost)
        self._draw_body_arrow(ghost)

    def _draw_body_arrow(self, ghost: Ghost) -> None:
        """Petite pointe vers le corps physique, seulement au-dela d'une distance minimale."""
        delta_x = self.player.center_x - ghost.center_x
        delta_y = self.player.center_y - ghost.center_y
        distance = math.hypot(delta_x, delta_y)
        if distance < settings.GHOST_HOME_ARROW_MIN_DISTANCE:
            return
        direction_x = delta_x / distance
        direction_y = delta_y / distance
        tip_x = ghost.center_x + direction_x * settings.GHOST_HOME_ARROW_OFFSET
        tip_y = ghost.center_y + direction_y * settings.GHOST_HOME_ARROW_OFFSET
        back_x = tip_x - direction_x * settings.GHOST_HOME_ARROW_LENGTH
        back_y = tip_y - direction_y * settings.GHOST_HOME_ARROW_LENGTH
        half_width = settings.GHOST_HOME_ARROW_WIDTH / 2
        left_x = back_x - direction_y * half_width
        left_y = back_y + direction_x * half_width
        right_x = back_x + direction_y * half_width
        right_y = back_y - direction_x * half_width
        arcade.draw_triangle_filled(
            tip_x,
            tip_y,
            left_x,
            left_y,
            right_x,
            right_y,
            settings.COLOR_PLAYER,
        )

    def _hud_data(self) -> HudData:
        state = self.machine.state
        return HudData(
            level_name=self.level.name,
            state_label=STATE_LABELS[state],
            essence=self.session.progression.essence,
            ghost_level=self.session.progression.level,
            hint=self._hint_for(state),
            has_key=self.player.has_item(ItemKind.KEY),
            corpse_count=len(self.level.corpses),
            ghost_time_left=self.ghost.time_left if state is GameState.GHOST and self.ghost is not None else None,
            ghost_duration=self.ghost.stats.duration if self.ghost is not None else settings.GHOST_DURATION,
            leash_ratio=self.ghost.leash_ratio if self.ghost is not None else 0.0,
            fps=self._fps if settings.DEBUG_SHOW_FPS and not self._debug_enabled else None,
            dash_ratio=self.player.dash_ratio if state is GameState.PLAYING else None,
            dash_ready=self.player.dash_ready,
            dash_flash=self.player.dash_flash,
            controls="ghost" if state is GameState.GHOST else ("playing" if state is GameState.PLAYING else ""),
            pressed_keys=frozenset(self.held_keys),
            show_esprit=self.session.knows_esprit,
        )

    def _hint_for(self, state: GameState) -> str:
        if state is GameState.PLAYING:
            return self.level.hint
        if state is GameState.GHOST:
            return "R : ecourter le mode fantome et revenir au checkpoint"
        return ""

    def _sample_fps(self) -> None:
        """Moyenne glissante du FPS de dessin, independante de update_rate."""
        now = time.perf_counter()
        if self._last_draw_time > 0.0:
            elapsed = now - self._last_draw_time
            if elapsed > 0.0:
                instant = 1.0 / elapsed
                self._fps = instant if self._fps == 0.0 else self._fps * 0.9 + instant * 0.1
        self._last_draw_time = now

    def _debug_snapshot(self) -> DebugSnapshot:
        """Collecte FPS, etat, tuiles a l'ecran et positions pour l'overlay."""
        tiles_total = len(self.level.walls) + len(self.level.spectral_walls) + len(self.level.hazards)
        ghost = self.ghost
        seen: dict[str, int] = {}
        for enemy in self.level.enemies:
            seen[enemy.state.name] = seen.get(enemy.state.name, 0) + 1
        enemy_states = " ".join(f"{name}={count}" for name, count in seen.items())
        cam_x, cam_y = self.camera.world.position
        return DebugSnapshot(
            fps=self._fps,
            state=self.machine.state.name,
            player_x=self.player.center_x,
            player_y=self.player.center_y,
            player_vx=self.player.change_x,
            player_vy=self.player.change_y,
            on_ground=self.player.on_ground,
            alive=self.player.alive,
            ghost_x=ghost.center_x if ghost is not None else None,
            ghost_y=ghost.center_y if ghost is not None else None,
            ghost_time=ghost.time_left if ghost is not None else None,
            leash_ratio=ghost.leash_ratio if ghost is not None else 0.0,
            camera_x=cam_x,
            camera_y=cam_y,
            view_w=self.camera.world.viewport_width,
            view_h=self.camera.world.viewport_height,
            window_w=self.window.width,
            window_h=self.window.height,
            fullscreen=bool(self.window.fullscreen),
            tiles_visible=self.level.tiles_drawn,
            tiles_total=tiles_total,
            walls_visible=self.level.walls_drawn,
            walls_total=len(self.level.walls),
            enemies=len(self.level.enemies),
            items=len(self.level.items),
            corpses=len(self.level.corpses),
            enemy_states=enemy_states,
            deaths=self.session.deaths,
            essence=self.session.progression.essence,
            extra=(f"chunks {self.level.chunks_drawn}/{self.level.chunks_total}",),
        )

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def on_update(self, delta_time: float) -> None:
        state = self.machine.state
        attractor: arcade.Sprite | None = None
        if state is GameState.PLAYING and self.player.alive:
            attractor = self.player
        elif state is GameState.GHOST and self.ghost is not None and not self.ghost.vanishing:
            attractor = self.ghost
        self.level.update(delta_time, attractor)
        if state is GameState.PLAYING:
            self._update_playing(delta_time)
        elif state is GameState.GHOST:
            self._update_ghost(delta_time)
        elif state is GameState.RESPAWNING:
            self._update_respawning(delta_time)
        self.atmosphere.update(delta_time)

    def _update_playing(self, delta_time: float) -> None:
        self.player.walk(self._horizontal_input())
        self.player.update(delta_time)
        self._update_enemies(delta_time)
        self._resolve_player_collisions()
        if self.machine.state is GameState.PLAYING:
            self.camera.follow(self.player, delta_time)

    def _update_ghost(self, delta_time: float) -> None:
        ghost = self.ghost
        if ghost is None:
            return
        ghost.steer(self._horizontal_input(), self._vertical_input())
        if self.anchor_corpse is not None and self.anchor_corpse.time_left > 0:
            ghost.anchor = (self.anchor_corpse.center_x, self.anchor_corpse.center_y)
        ghost.update(delta_time)
        self._update_enemies(delta_time)
        if not ghost.vanishing:
            self._resolve_ghost_collisions(ghost)
        self.camera.follow(ghost, delta_time)
        if ghost.expired:
            emit_ghost_end(self, "timer")
        elif ghost.vanished:
            emit_ghost_end(self, "manual")

    def _update_respawning(self, delta_time: float) -> None:
        if self.ghost is not None:
            self.ghost.update(delta_time)
            if self.ghost.vanished:
                self.ghost = None
        self._respawn_timer -= delta_time
        if self._respawn_timer > 0:
            return
        self.ghost = None
        self.player.respawn_at(self.player.respawn_point)
        for kind in self._delivered_items:
            self.player.give_item(kind)
        self._delivered_items.clear()
        self._update_respawn_enemies()
        self.camera.snap_to(self.player)
        self.machine.try_to(GameState.PLAYING)

    def _update_enemies(self, delta_time: float) -> None:
        for enemy in list(self.level.enemies):
            enemy.update(delta_time, player=self.player, corpses=self.level.corpses)

    def _update_respawn_enemies(self) -> None:
        for enemy, spawn_x, spawn_y in self._enemy_spawns:
            enemy.respawn(spawn_x, spawn_y)
            if enemy not in self.level.enemies:
                self.level.enemies.append(enemy)
            

    # ------------------------------------------------------------------ #
    # Consequences des collisions
    # ------------------------------------------------------------------ #

    def _resolve_player_collisions(self) -> None:
        stomped = collisions.enemy_stomped_by_player(self.player, self.level.enemies)
        if stomped is not None:
            orb = stomped.take_damage()
            if orb is not None:
                self.level.spawn_item(orb)
            self.player.change_y = settings.PLAYER_JUMP_SPEED * 0.6

        for item in collisions.items_reachable_by_body(self.player, self.level):
            self._collect(item.kind)
            item.remove_from_sprite_lists()

        checkpoint = collisions.checkpoint_touched_by_player(self.player, self.level)
        if checkpoint is not None:
            self.player.respawn_point = (checkpoint.center_x, checkpoint.center_y)
            checkpoint.activate()

        door = collisions.door_touched_by_player(self.player, self.level)
        if door is not None and self.player.has_item(ItemKind.KEY):
            door.unlock()
            emit_player_win(self)
            return

        if collisions.player_hits_hazard(self.player, self.level):
            emit_player_death(self, "spikes")
        elif collisions.player_out_of_bounds(self.player, self.level):
            emit_player_death(self, "out_of_bounds")
        elif collisions.enemy_touching_player(self.player, self.level.enemies) is not None:
            emit_player_death(self, "enemy")

    def _resolve_ghost_collisions(self, ghost: Ghost) -> None:
        for item in collisions.items_reachable_by_ghost(ghost, self.level):
            ghost.pick_up(item)

        if not ghost.carried:
            return
        corpse = collisions.corpse_touched_by_ghost(ghost, self.level.corpses)
        if corpse is None:
            return
        for item in ghost.release_all():
            self._collect(item.kind)
            item.remove_from_sprite_lists()

    def _collect(self, kind: ItemKind) -> None:
        """Applique l'effet du ramassage d'un objet.

        Les objets ramasses pendant le mode fantome sont mis de cote et remis au
        corps physique a la reapparition.
        """
        if kind is ItemKind.SOUL_ORB:
            self.session.progression.absorb_orb()
            return
        if self.machine.state is GameState.GHOST:
            self._delivered_items.append(kind)
        else:
            self.player.give_item(kind)

    # ------------------------------------------------------------------ #
    # Entrees clavier
    # ------------------------------------------------------------------ #

    def _horizontal_input(self) -> int:
        direction = 0
        if self.held_keys & _LEFT_KEYS:
            direction -= 1
        if self.held_keys & _RIGHT_KEYS:
            direction += 1
        return direction

    def _vertical_input(self) -> int:
        direction = 0
        if self.held_keys & _DOWN_KEYS:
            direction -= 1
        if self.held_keys & _UP_KEYS:
            direction += 1
        return direction

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        from src.ui.menus import TitleView

        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.F3:
            self._debug_enabled = not self._debug_enabled
            return
        self.held_keys.add(symbol)
        state = self.machine.state
        if symbol == arcade.key.ESCAPE:
            self.window.show_view(TitleView(self.session))
            return
        if state is GameState.PLAYING:
            if symbol in _JUMP_KEYS:
                self.player.jump()
            elif symbol in _DASH_KEYS:
                if self.player.dash():
                    self.camera.shake(
                        settings.CAMERA_DASH_SHAKE, settings.CAMERA_DASH_SHAKE_TIME
                    )
            elif symbol == _PROJECT_KEY:
                emit_player_death(self, "sacrifice")
        elif state is GameState.GHOST and symbol == _RETURN_KEY:
            if self.ghost is not None:
                self.ghost.start_vanish()

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        self.held_keys.discard(symbol)
        if symbol in _JUMP_KEYS and self.machine.state is GameState.PLAYING:
            self.player.cut_jump()

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        self.camera.on_resize(width, height)
