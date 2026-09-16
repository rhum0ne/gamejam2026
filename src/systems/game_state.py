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
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto

import arcade

import settings
from src.entities.batch_draw import SpriteOverlay
from src.entities.corpse import Corpse
from src.entities.ghost import Ghost
from src.entities.glow import glow_pass
from src.entities.item import ItemKind
from src.entities.player import Player
from src.systems import collisions
from src.systems.ghost_emergence import GhostEmergence
from src.systems.player_rebirth import PlayerRebirth
from src.systems.play_events import bind_play_view, emit_ghost_end, emit_player_death, emit_player_win
from src.systems.upgrades import SoulProgression
from src.ui.debug import DebugOverlay, DebugSnapshot
from src.ui.display import handle_display_key
from src.ui.hud import Hud, HudData
from src.ui.sprites import draw_pixel_sprite
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
    PAUSED = auto()
    VICTORY = auto()
    GAME_OVER = auto()


_TRANSITIONS: dict[GameState, frozenset[GameState]] = {
    GameState.MENU: frozenset({GameState.PLAYING}),
    GameState.PLAYING: frozenset(
        {GameState.GHOST, GameState.VICTORY, GameState.GAME_OVER, GameState.MENU, GameState.PAUSED}
    ),
    GameState.GHOST: frozenset(
        {GameState.RESPAWNING, GameState.GAME_OVER, GameState.MENU, GameState.PAUSED}
    ),
    GameState.RESPAWNING: frozenset({GameState.PLAYING, GameState.MENU, GameState.PAUSED}),
    GameState.PAUSED: frozenset(
        {GameState.PLAYING, GameState.GHOST, GameState.RESPAWNING, GameState.MENU}
    ),
    GameState.VICTORY: frozenset({GameState.PLAYING, GameState.MENU}),
    GameState.GAME_OVER: frozenset({GameState.PLAYING, GameState.MENU}),
}

STATE_LABELS: dict[GameState, str] = {
    GameState.MENU: "Menu",
    GameState.PLAYING: "Corps physique",
    GameState.GHOST: "Projection astrale",
    GameState.RESPAWNING: "Retour au corps...",
    GameState.PAUSED: "Pause",
    GameState.VICTORY: "Niveau termine",
    GameState.GAME_OVER: "Game Over",
}


def _in_view(sprite: arcade.Sprite, view, pad: float) -> bool:
    """True si le sprite, plus une marge de halo, chevauche le viewport."""
    return not (
        sprite.center_x < view.left - pad
        or sprite.center_x > view.right + pad
        or sprite.center_y < view.bottom - pad
        or sprite.center_y > view.top + pad
    )


def _mechanism_in_view(mechanism, view, pad: float) -> bool:
    """True si la plaque, une cible ou le lien entre les deux touche l'ecran."""
    xs = [mechanism.plate.center_x]
    ys = [mechanism.plate.center_y]
    for tile in mechanism.targets:
        xs.append(tile.sprite.center_x)
        ys.append(tile.sprite.center_y)
    return not (
        max(xs) < view.left - pad
        or min(xs) > view.right + pad
        or max(ys) < view.bottom - pad
        or min(ys) > view.top + pad
    )


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
    # Carte jouee a la place de LEVEL_SEQUENCE (essai depuis l'editeur).
    map_override: str | None = None
    # Si renseigne, Echap (et l'ecran de victoire) ramene a l'appelant.
    on_leave: Callable[[], None] | None = None

    @property
    def level_file(self) -> str:
        if self.map_override:
            return self.map_override
        return settings.LEVEL_SEQUENCE[self.level_index]

    @property
    def is_last_level(self) -> bool:
        if self.map_override:
            return True
        return self.level_index >= len(settings.LEVEL_SEQUENCE) - 1

    def advance_level(self) -> bool:
        """Passe au niveau suivant. Retourne False si l'aventure est terminee."""
        if self.is_last_level:
            return False
        self.level_index += 1
        return True

    def start_level(self, index: int) -> None:
        """Place la session sur un niveau de `LEVEL_SEQUENCE`."""
        if not 0 <= index < len(settings.LEVEL_SEQUENCE):
            raise ValueError(
                f"index de niveau invalide : {index} "
                f"(0..{len(settings.LEVEL_SEQUENCE) - 1})"
            )
        self.level_index = index
        self.map_override = None

    def restart(self) -> None:
        """Remet la session a zero (nouvelle partie depuis le menu titre)."""
        self.progression = SoulProgression()
        self.level_index = 0
        self.deaths = 0
        self.knows_esprit = False
        self.map_override = None
        self.on_leave = None


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
        self._reveal_walls = SpriteOverlay()
        self._reveal_actors = SpriteOverlay()
        self.level: Level
        self.player: Player
        self.ghost: Ghost | None = None
        self.anchor_corpse: Corpse | None = None
        self._emergence: GhostEmergence | None = None
        self._rebirth: PlayerRebirth | None = None
        self.held_keys: set[int] = set()
        self._delivered_items: list[ItemKind] = []
        self._pause_menu = None
        self._paused_from = GameState.PLAYING
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
            if checkpoint.spawn_point == self.level.checkpoint_spawn:
                self.level.activate_checkpoint(checkpoint, ignite=False)
                break
        self.player.bind_world(self.level.static_walls, platforms=[self.level.corpses])
        for enemy in self.level.enemies:
            enemy.bind_world(self._static_platforms(), hazards=self.level.hazards)
        self.level.prepare_draw()
        self.camera.set_bounds(self.level.width, self.level.height)
        self._enemy_spawns = [(enemy, enemy.center_x, enemy.center_y) for enemy in self.level.enemies]
        self.camera.snap_to(self.player)
        self.ghost = None
        self.anchor_corpse = None
        self._emergence = None
        self._rebirth = None
        self.held_keys.clear()
        self._delivered_items.clear()
        self.machine = GameStateMachine(GameState.MENU)
        self.machine.to(GameState.PLAYING)

    @property
    def ghost_emerging(self) -> bool:
        return self._emergence is not None and self._emergence.active

    @property
    def player_rebirthing(self) -> bool:
        return self._rebirth is not None and self._rebirth.active

    def start_ghost_emergence(self, origin_x: float, origin_y: float) -> None:
        """Lance le gros plan, les particules et la sortie du fantome."""
        if self.ghost is not None:
            self.ghost.begin_emerge()
        sequence = GhostEmergence(origin_x, origin_y)
        sequence.capture_zoom(self.camera)
        self._emergence = sequence

    def start_player_rebirth(self, origin_x: float, origin_y: float) -> None:
        """Lance le voile noir et la reconstruction du corps au checkpoint."""
        self._rebirth = PlayerRebirth(origin_x, origin_y)

    def _static_platforms(self) -> list[arcade.SpriteList]:
        """Plateformes solides hors cadavres (un cadavre ne doit pas se bloquer lui-meme)."""
        return [self.level.walls, self.level.spectral_walls]

    def _terrain_cull_rect(self):
        """Chunks a dessiner : ecran + marge, et le trou de vision en fantome.

        Hors du voile le decor est presque noir : le dessiner quand meme
        coutait ~5 ms et faisait chuter le FPS a 45.
        """
        view = self.camera.cull_rect()
        ghost = self.ghost
        if (
            self.machine.state is not GameState.GHOST
            or ghost is None
            or self.ghost_emerging
        ):
            return view
        radius = ghost.vision_radius + settings.RENDER_CULL_PAD
        return self.camera.cull_rect_around(ghost.center_x, ghost.center_y, radius)

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #

    def on_draw(self) -> None:
        self._sample_fps()
        rebirth = self._rebirth if self.player_rebirthing else None
        defer_player = rebirth is not None and rebirth.shows_player
        self.camera.begin_frame()
        self.camera.use_world()
        tight_cull = (
            self.machine.state is GameState.GHOST
            and not self.ghost_emerging
            and (rebirth is None or rebirth.shows_world)
        )
        if rebirth is None or rebirth.shows_world:
            self.level.draw(self._terrain_cull_rect(), tight_cull=tight_cull)
            if self.player.alive and not defer_player:
                self.player.draw_fx()
                draw_pixel_sprite(self.player)
                self.player.draw_particles()
            # Premier plan : passe devant le monde, reste sous le voile fantome et le HUD.
            self.atmosphere.draw(self.camera.world)
            if self.ghost is not None:
                if self.machine.state is GameState.GHOST:
                    self._draw_ghost_or_emergence(self.ghost)
                elif self.ghost.vanishing:
                    draw_pixel_sprite(self.ghost)
            if settings.DEBUG_SHOW_HITBOXES:
                self._draw_hitboxes()
        self.camera.use_ui()
        if rebirth is None:
            self._draw_hud_layer()
        elif rebirth.covers_hud:
            self._draw_hud_layer()
            self._draw_black_veil(rebirth.veil)
        else:
            self._draw_black_veil(rebirth.veil)
        if defer_player:
            self.camera.use_world()
            self._draw_rebirth_body(rebirth)
        if rebirth is not None and not rebirth.covers_hud and rebirth.hud_alpha > 0.0:
            self.camera.use_ui()
            self._draw_hud_layer(rebirth.hud_alpha)
        if self.machine.state is GameState.PAUSED:
            self.camera.use_ui()
            self._pause_overlay().draw(settings.WORLD_VIEW_WIDTH, settings.WORLD_VIEW_HEIGHT)
        warp = 0.0
        if self.machine.state is GameState.GHOST and self.ghost is not None:
            warp = self.ghost.warp_strength
            emergence = self._emergence
            if emergence is not None and emergence.active:
                warp *= emergence.fog_strength
        self.camera.present(warp)

    def _draw_hud_layer(self, fade: float = 1.0) -> None:
        self.hud.draw(self._hud_data(), fade=fade)
        if self._debug_enabled and fade > 0.05:
            self.debug.draw(self._debug_snapshot())

    def _draw_black_veil(self, strength: float) -> None:
        alpha = int(255 * max(0.0, min(1.0, strength)))
        if alpha <= 0:
            return
        arcade.draw_lrbt_rectangle_filled(
            0,
            settings.WORLD_VIEW_WIDTH,
            0,
            settings.WORLD_VIEW_HEIGHT,
            (*settings.COLOR_REBIRTH_VEIL, alpha),
        )

    def _draw_rebirth_body(self, rebirth: PlayerRebirth) -> None:
        """Corps et motes par-dessus le voile : le joueur apparait avant le decor."""
        fade = rebirth.player_alpha
        if self.player.alive and fade > 0.0:
            self.player.alpha = int(255 * fade)
            self.player.draw_fx()
            draw_pixel_sprite(self.player)
            self.player.draw_particles()
            self.player.alpha = 255
        rebirth.draw_fx()

    def _draw_hitboxes(self) -> None:
        color = settings.COLOR_DEBUG_HITBOX
        view_rect = self.camera.visible_rect()
        self.level.draw_static_hit_boxes(color, view_rect)
        self.level.enemies.draw_hit_boxes(color)
        self.level.corpses.draw_hit_boxes(color)
        self.level.plates.draw_hit_boxes(color)
        self.level.falling_spikes.draw_hit_boxes(color)
        for thrower in self.level.flamethrowers:
            if thrower.is_lethal:
                left, right, bottom, top = thrower.flame_bounds()
                arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, color, 1)
        if self.player.alive:
            self.player.draw_hit_box(color)
        if self.ghost is not None:
            self.ghost.draw_hit_box(color)

    def _draw_ghost_or_emergence(self, ghost: Ghost) -> None:
        """Voile du fantome, ou cinematique de sortie hors du corps."""
        emergence = self._emergence
        if emergence is None or not emergence.active:
            self._draw_ghost_layer(ghost)
            return
        fade = emergence.player_fade
        if fade > 0.0:
            self.player.alpha = int(255 * fade)
            draw_pixel_sprite(self.player)
            self.player.alpha = 255
        if emergence.shows_fog:
            self._draw_ghost_layer(ghost)
        elif ghost.alpha > 0:
            with glow_pass():
                ghost.draw_fx()
            draw_pixel_sprite(ghost)
        emergence.draw_fx()

    def _draw_ghost_layer(self, ghost: Ghost) -> None:
        """Voile radial, menaces rouges hors champ, secrets dans le champ, fantome."""
        revealed_walls: list[arcade.Sprite] = []
        for wall in self.level.spectral_walls:
            wall.set_revealed(ghost.reveals(wall))
            if wall.revealed:
                revealed_walls.append(wall)
        self.fog.draw(ghost, self.camera.world)
        self._reveal_walls.draw(revealed_walls)
        with glow_pass():
            for item in self.level.items:
                if ghost.reveals(item):
                    item.draw_fx()
            self._draw_threat_glows()
            self._draw_mechanism_hints()
            ghost.draw_fx()
        revealed_actors: list[arcade.Sprite] = []
        for item in self.level.items:
            if ghost.reveals(item):
                revealed_actors.append(item)
        for enemy in self.level.enemies:
            if ghost.reveals(enemy):
                revealed_actors.append(enemy)
        self._reveal_actors.draw(revealed_actors)
        draw_pixel_sprite(ghost)
        self._draw_body_arrow(ghost)

    def _draw_threat_glows(self) -> None:
        """Piques et ennemis : meme halo rouge, au-dessus du voile, tout l'ecran."""
        view = self.camera.cull_rect()
        pad = settings.HAZARD_GHOST_GLOW_SIZE
        for spike in self.level.hazards:
            if _in_view(spike, view, pad):
                spike.draw_ghost_glow(bind_blend=False)
        for spike in self.level.falling_spikes:
            if _in_view(spike, view, pad):
                spike.draw_ghost_glow(bind_blend=False)
        for thrower in self.level.flamethrowers:
            if _in_view(thrower, view, pad):
                thrower.draw_ghost_glow(bind_blend=False)
        for enemy in self.level.enemies:
            if _in_view(enemy, view, pad):
                enemy.draw_ghost_glow(bind_blend=False)

    def _draw_mechanism_hints(self) -> None:
        """Plaque lumineuse et vrille fantome vers les paquets, hors du voile."""
        now = time.perf_counter()
        view = self.camera.cull_rect()
        pad = settings.RENDER_CULL_PAD
        for mechanism in self.level.mechanisms:
            if not _mechanism_in_view(mechanism, view, pad):
                continue
            mechanism.draw_soul(now)

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
        show_body_hud = state is GameState.PLAYING or (
            self.player_rebirthing and self.player.alive
        )
        return HudData(
            level_name=self.level.name,
            state_label=STATE_LABELS[state],
            essence=self.session.progression.essence,
            ghost_level=self.session.progression.level,
            hint=self._hint_for(state),
            has_key=self.player.has_item(ItemKind.KEY),
            corpse_count=len(self.level.corpses),
            ghost_time_left=(
                self.ghost.time_left
                if state is GameState.GHOST
                and self.ghost is not None
                and not self.ghost_emerging
                else None
            ),
            ghost_duration=self.ghost.stats.duration if self.ghost is not None else settings.GHOST_DURATION,
            leash_ratio=self.ghost.leash_ratio if self.ghost is not None else 0.0,
            fps=self._fps if settings.DEBUG_SHOW_FPS and not self._debug_enabled else None,
            controls=(
                "ghost"
                if state is GameState.GHOST and not self.ghost_emerging
                else ("playing" if show_body_hud else "")
            ),
            pressed_keys=frozenset(self.held_keys),
            show_esprit=self.session.knows_esprit,
        )

    def _hint_for(self, state: GameState) -> str:
        if state is GameState.PLAYING or (
            state is GameState.RESPAWNING and self.player.alive
        ):
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
        if self.machine.state is GameState.PAUSED:
            return
        state = self.machine.state
        attractor: arcade.Sprite | None = None
        if state is GameState.PLAYING and self.player.alive:
            attractor = self.player
        elif (
            state is GameState.GHOST
            and self.ghost is not None
            and not self.ghost.vanishing
            and not self.ghost_emerging
        ):
            attractor = self.ghost
        self.level.update(delta_time, attractor)
        self._update_mechanisms()
        self.level.update_spikes()
        if state is GameState.PLAYING:
            self._update_playing(delta_time)
        elif state is GameState.GHOST:
            self._update_ghost(delta_time)
        elif state is GameState.RESPAWNING:
            self._update_respawning(delta_time)
        self._resolve_falling_spike_kills()
        self._resolve_flame_kills()
        self.atmosphere.update(delta_time)

    def _mechanism_weights(self) -> list[arcade.Sprite]:
        """Corps, cadavres et ennemis : le fantome ne pese pas sur les plaques."""
        weights: list[arcade.Sprite] = []
        if self.player.alive:
            weights.append(self.player)
        weights.extend(self.level.corpses)
        weights.extend(self.level.enemies)
        return weights

    def _update_mechanisms(self) -> None:
        if not self.level.mechanisms:
            return
        weights = self._mechanism_weights()
        for mechanism in self.level.mechanisms:
            pressed = collisions.plate_is_weighted(mechanism.plate, weights)
            mechanism.set_pressed(pressed, weights)

    def _update_playing(self, delta_time: float) -> None:
        self.player.walk(self._horizontal_input())
        self.player.update(delta_time)
        self._block_hazard_sides()
        self._update_enemies(delta_time)
        self._resolve_player_collisions()
        if self.machine.state is GameState.PLAYING:
            self.camera.follow(self.player, delta_time, zoom=settings.CAMERA_ZOOM_PLAYER)

    def _block_hazard_sides(self) -> None:
        """Une pique bloque comme un mur si on la touche par le cote (cf Mario)."""
        player = self.player
        for hazard in collisions.hazard_side_contacts(player, self.level):
            overlap = min(player.right, hazard.right) - max(player.left, hazard.left)
            if overlap <= 0:
                continue
            if player.center_x < hazard.center_x:
                player.center_x -= overlap
            else:
                player.center_x += overlap
            player.change_x = 0.0

    def _update_ghost(self, delta_time: float) -> None:
        ghost = self.ghost
        if ghost is None:
            return
        if self._update_emergence(delta_time, ghost):
            return
        ghost.steer(self._horizontal_input(), self._vertical_input())
        if self.anchor_corpse is not None and self.anchor_corpse.time_left > 0:
            ghost.anchor = (self.anchor_corpse.center_x, self.anchor_corpse.center_y)
        ghost.update(delta_time)
        self._update_enemies(delta_time)
        if not ghost.vanishing:
            self._resolve_ghost_collisions(ghost)
        self.camera.follow(ghost, delta_time, zoom=settings.CAMERA_ZOOM_GHOST)
        if ghost.expired:
            emit_ghost_end(self, "timer")
        elif ghost.vanished:
            emit_ghost_end(self, "manual")

    def _update_emergence(self, delta_time: float, ghost: Ghost) -> bool:
        """Avance la cinematique. True tant qu'elle bloque le pilotage."""
        emergence = self._emergence
        if emergence is None:
            return False
        emergence.update(delta_time, self.camera, ghost)
        if emergence.active:
            return True
        self._emergence = None
        return False

    def _update_respawning(self, delta_time: float) -> None:
        if self.ghost is not None:
            self.ghost.update(delta_time)
            if self.ghost.vanished:
                self.ghost = None
        rebirth = self._rebirth
        if rebirth is None:
            self._finish_rebirth()
            return
        rebirth.update(delta_time, self.camera)
        if rebirth.consume_body_spawn():
            self._materialize_body()
        if rebirth.active:
            return
        self._rebirth = None
        self._finish_rebirth()

    def _materialize_body(self) -> None:
        """Place le corps au checkpoint une fois l'ecran noir."""
        self.ghost = None
        origin_x, origin_y = self.player.respawn_point
        self.player.respawn_at((origin_x, origin_y))
        for kind in self._delivered_items:
            self.player.give_item(kind)
        self._delivered_items.clear()
        checkpoint = self.level.checkpoint_at(self.player.respawn_point)
        if checkpoint is not None:
            checkpoint.play_respawn()
        rebirth = self._rebirth
        if rebirth is not None:
            rebirth.particles.emit_cloud(origin_x, origin_y)
        self.camera.snap_to(self.player, zoom=settings.CAMERA_ZOOM_REBIRTH)

    def _finish_rebirth(self) -> None:
        if not self.player.alive:
            self.player.respawn_at(self.player.respawn_point)
            for kind in self._delivered_items:
                self.player.give_item(kind)
            self._delivered_items.clear()
        self._update_respawn_enemies()
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
            self.player.respawn_point = checkpoint.spawn_point
            self.level.activate_checkpoint(checkpoint)

        door = collisions.door_touched_by_player(self.player, self.level)
        if door is not None and self.player.has_item(ItemKind.KEY):
            door.unlock()
            emit_player_win(self)
            return

        if collisions.player_hits_hazard(self.player, self.level):
            emit_player_death(self, "spikes")
        elif collisions.player_hits_flame(self.player, self.level.flamethrowers):
            emit_player_death(self, "flame")
        elif collisions.player_out_of_bounds(self.player, self.level):
            emit_player_death(self, "out_of_bounds")
        elif collisions.enemy_striking_player(self.player, self.level.enemies) is not None:
            emit_player_death(self, "enemy")

    def _resolve_falling_spike_kills(self) -> None:
        """Une pique en chute tue les ennemis (le joueur est deja gere via les hazards)."""
        for enemy in collisions.enemies_hit_by_falling_spikes(
            self.level.enemies, self.level.falling_spikes
        ):
            orb = enemy.take_damage()
            if orb is not None:
                self.level.spawn_item(orb)

    def _resolve_flame_kills(self) -> None:
        """Le jet tue les ennemis (le joueur est gere dans les collisions corps)."""
        for enemy in collisions.enemies_hit_by_flame(
            self.level.enemies, self.level.flamethrowers
        ):
            orb = enemy.take_damage()
            if orb is not None:
                self.level.spawn_item(orb)

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
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.F3:
            self._debug_enabled = not self._debug_enabled
            return
        if self.machine.state is GameState.PAUSED:
            self._pause_overlay().on_key_press(self.window, symbol, modifiers)
            return
        self.held_keys.add(symbol)
        state = self.machine.state
        if symbol == arcade.key.ESCAPE:
            if self.session.on_leave is not None:
                self.session.on_leave()
                return
            self.enter_pause()
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
            if self.ghost_emerging:
                return
            if self.ghost is not None:
                self.ghost.start_vanish()

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        self.held_keys.discard(symbol)
        if self.machine.state is GameState.PAUSED:
            return
        if symbol in _JUMP_KEYS and self.machine.state is GameState.PLAYING:
            self.player.cut_jump()

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        if self.machine.state is not GameState.PAUSED:
            return
        ui_x, ui_y = self.camera.window_to_ui(x, y)
        self._pause_overlay().on_mouse_motion(ui_x, ui_y)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        if self.machine.state is not GameState.PAUSED:
            return
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        ui_x, ui_y = self.camera.window_to_ui(x, y)
        self._pause_overlay().on_mouse_press(ui_x, ui_y)

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int) -> None:
        if self.machine.state is not GameState.PAUSED:
            return
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        ui_x, ui_y = self.camera.window_to_ui(x, y)
        self._pause_overlay().on_mouse_release(ui_x, ui_y)

    def _pause_overlay(self):
        if self._pause_menu is None:
            from src.ui.pause import PauseMenu

            self._pause_menu = PauseMenu(
                on_resume=self.leave_pause,
                on_retry=self._retry_from_pause,
                on_quit=self._quit_from_pause,
            )
        return self._pause_menu

    def enter_pause(self) -> None:
        if self.machine.state is GameState.PAUSED:
            return
        if not self.machine.can(GameState.PAUSED):
            return
        self._paused_from = self.machine.state
        self.held_keys.clear()
        self.machine.try_to(GameState.PAUSED)

    def leave_pause(self) -> None:
        if self.machine.state is not GameState.PAUSED:
            return
        self.machine.try_to(self._paused_from)

    def _retry_from_pause(self) -> None:
        self.setup()

    def _quit_from_pause(self) -> None:
        from src.ui.menus import TitleView

        self.window.show_view(TitleView(self.session))

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        self.camera.on_resize(width, height)
