"""Le corps physique du joueur.

Responsabilites : deplacement lateral, saut (avec coyote time), gravite via
`arcade.PhysicsEnginePlatformer`, dash, inventaire et etat vivant / mort.

Ce module ne connait ni le fantome ni les etats de jeu : la transition
"mort -> mode fantome" est orchestree par `src.systems.game_state`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import arcade

import settings
from src.entities.glow import draw_glow
from src.entities.item import ItemKind
from src.ui import sprites


def _idle_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(settings.SPRITE_PLAYER_IDLE, settings.SPRITE_FRAME_SIZE)
    return sprites.StripAnimation(frames, settings.ANIM_IDLE_FRAME_TIME, loop=True)


def _walk_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(settings.SPRITE_PLAYER_WALK, settings.SPRITE_FRAME_SIZE)
    return sprites.StripAnimation(frames, settings.ANIM_WALK_FRAME_TIME, loop=True)

def _exp_alpha(delta_time: float, smooth_time: float) -> float:
    if smooth_time <= 0.0:
        return 1.0
    return 1.0 - math.exp(-max(delta_time, 0.0) / smooth_time)


def _approach(current: float, target: float, max_delta: float) -> float:
    if current < target:
        return min(current + max_delta, target)
    return max(current - max_delta, target)


class Player(arcade.Sprite):
    """Corps physique controle au clavier."""

    def __init__(self, center_x: float, center_y: float) -> None:
        self._idle = _idle_animation()
        self._walk = _walk_animation()
        super().__init__(self._idle.textures[0], center_x=center_x, center_y=center_y)
        sprites.apply_rect_hit_box(self, settings.PLAYER_WIDTH, settings.PLAYER_HEIGHT)
        self.scale = settings.ENTITY_SCALE
        self._animator = sprites.Animator(self._idle)
        self.alive = True
        self.facing = 1
        self.inventory: set[ItemKind] = set()
        self.respawn_point: tuple[float, float] = (center_x, center_y)
        self._physics: arcade.PhysicsEnginePlatformer | None = None
        self._time_off_ground = 0.0
        self._place_on_tile(center_x, center_y)
        self._was_on_ground = True
        self._move_dir = 0
        self._landing_timer = 0.0
        self._dash_timer = 0.0
        self._dash_dir = 1
        self._dash_cooldown = 0.0
        self._ready_flash = 0.0
        self._trail: list[list[float]] = []

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(
        self,
        walls: Sequence[arcade.SpriteList],
        platforms: Sequence[arcade.SpriteList] | None = None,
    ) -> None:
        """Branche le moteur de physique sur le terrain et les plateformes mobiles.

        `walls` doit etre du terrain immobile (hash spatial). Les cadavres passent
        dans `platforms` : Arcade les traite sans reconstruire le hash a chaque frame.
        """
        self._physics = arcade.PhysicsEnginePlatformer(
            self,
            walls=list(walls),
            platforms=list(platforms) if platforms else None,
            gravity_constant=settings.PLAYER_GRAVITY,
        )

    def _place_on_tile(self, center_x: float, center_y: float) -> None:
        """Pose les pieds sur le bas de la tuile dont `center` est le milieu."""
        self.center_x = center_x
        self.center_y = center_y - settings.TILE_SIZE / 2 + abs(self.height) / 2

    # ------------------------------------------------------------------ #
    # Etat
    # ------------------------------------------------------------------ #

    @property
    def on_ground(self) -> bool:
        return self._physics is not None and self._physics.can_jump()

    @property
    def is_dashing(self) -> bool:
        return self._dash_timer > 0.0

    @property
    def dash_ratio(self) -> float:
        """1.0 = dash pret, 0.0 = vient d'etre utilise."""
        cooldown = settings.PLAYER_DASH_COOLDOWN
        if cooldown <= 0.0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - self._dash_cooldown / cooldown))

    @property
    def dash_ready(self) -> bool:
        return self._dash_cooldown <= 0.0 and not self.is_dashing

    @property
    def dash_flash(self) -> float:
        """Intensite 0-1 de l'effet visuel 'dash pret'."""
        duration = settings.PLAYER_DASH_READY_FLASH
        if duration <= 0.0:
            return 0.0
        return max(0.0, min(1.0, self._ready_flash / duration))

    def has_item(self, kind: ItemKind) -> bool:
        return kind in self.inventory

    def give_item(self, kind: ItemKind) -> None:
        self.inventory.add(kind)

    def die(self) -> None:
        """Marque le corps comme mort et l'immobilise."""
        self.alive = False
        self.change_x = 0.0
        self.change_y = 0.0
        self._move_dir = 0
        self._dash_timer = 0.0
        self._landing_timer = 0.0
        self._trail.clear()

    def respawn_at(self, position: tuple[float, float]) -> None:
        """Fait reapparaitre le corps au checkpoint fourni."""
        self.alive = True
        self._place_on_tile(*position)
        self.change_x = 0.0
        self.change_y = 0.0
        self._time_off_ground = 0.0
        self._was_on_ground = True
        self._move_dir = 0
        self._landing_timer = 0.0
        self._dash_timer = 0.0
        self._dash_cooldown = 0.0
        self._ready_flash = 0.0
        self._trail.clear()

    # ------------------------------------------------------------------ #
    # Commandes
    # ------------------------------------------------------------------ #

    def walk(self, direction: int) -> None:
        """Enregistre la direction horizontale : -1 (gauche), 0, ou 1 (droite)."""
        self._move_dir = 0 if direction == 0 else (1 if direction > 0 else -1)
        if self._move_dir != 0:
            self.facing = self._move_dir

    def dash(self) -> bool:
        """Impulse un dash dans la direction actuelle. False si en cooldown."""
        if not self.alive or self.is_dashing or self._dash_cooldown > 0.0:
            return False
        if self._move_dir != 0:
            self._dash_dir = self._move_dir
        elif abs(self.change_x) > 0.2:
            self._dash_dir = 1 if self.change_x > 0 else -1
        else:
            self._dash_dir = self.facing
        self.facing = self._dash_dir
        self._dash_timer = settings.PLAYER_DASH_DURATION
        self._dash_cooldown = settings.PLAYER_DASH_COOLDOWN
        self._ready_flash = 0.0
        self.change_x = self._dash_dir * settings.PLAYER_DASH_SPEED
        self._trail.append([self.center_x, self.center_y, settings.PLAYER_DASH_TRAIL_LIFE])
        return True

    def jump(self) -> bool:
        """Tente un saut. Retourne True si le saut a ete declenche."""
        if not self.alive or self._physics is None:
            return False
        if self._time_off_ground > settings.PLAYER_COYOTE_TIME:
            return False
        self._physics.jump(settings.PLAYER_JUMP_SPEED)
        self._time_off_ground = settings.PLAYER_COYOTE_TIME + 1.0
        self._was_on_ground = False
        return True

    def cut_jump(self) -> None:
        """Ecourte le saut quand la touche est relachee (saut a hauteur variable)."""
        if self.change_y > 0 and not self.is_dashing:
            self.change_y *= 0.4

    def draw_fx(self) -> None:
        """Trainee de dash (afterimages + halo) et anneau quand la jauge est pleine."""
        life_max = max(settings.PLAYER_DASH_TRAIL_LIFE, 0.001)
        for pos_x, pos_y, life in self._trail:
            fade = max(0.0, min(1.0, life / life_max))
            width = settings.PLAYER_WIDTH * (0.42 + 0.38 * fade)
            height = settings.PLAYER_HEIGHT * (0.5 + 0.35 * fade)
            draw_glow(
                pos_x,
                pos_y,
                width * settings.PLAYER_DASH_TRAIL_GLOW_SCALE,
                height * settings.PLAYER_DASH_TRAIL_GLOW_SCALE,
                settings.COLOR_DASH_GLOW,
                int(settings.PLAYER_DASH_TRAIL_GLOW_ALPHA * fade),
            )
            arcade.draw_lrbt_rectangle_filled(
                pos_x - width / 2,
                pos_x + width / 2,
                pos_y - height / 2,
                pos_y + height / 2,
                (*settings.COLOR_DASH, int(100 * fade)),
            )
        if self.is_dashing:
            glow_w = (
                settings.PLAYER_WIDTH
                * settings.PLAYER_DASH_GLOW_SCALE
                * settings.PLAYER_DASH_GLOW_STRETCH
            )
            glow_h = settings.PLAYER_HEIGHT * settings.PLAYER_DASH_GLOW_SCALE
            draw_glow(
                self.center_x - self._dash_dir * settings.PLAYER_WIDTH * settings.PLAYER_DASH_GLOW_OFFSET,
                self.center_y,
                glow_w,
                glow_h,
                settings.COLOR_DASH_GLOW,
                settings.PLAYER_DASH_GLOW_ALPHA,
            )
            streak = 22.0
            if self._dash_dir >= 0:
                left, right = self.left - streak, self.left
            else:
                left, right = self.right, self.right + streak
            inset = settings.PLAYER_HEIGHT * 0.22
            arcade.draw_lrbt_rectangle_filled(
                left,
                right,
                self.bottom + inset,
                self.top - inset,
                (*settings.COLOR_DASH, 70),
            )
        flash = self.dash_flash
        if flash > 0.0:
            radius = 16.0 + (1.0 - flash) * 26.0
            arcade.draw_circle_outline(
                self.center_x,
                self.center_y,
                radius,
                (*settings.COLOR_DASH, int(220 * flash)),
                2,
            )

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        if not self.alive or self._physics is None:
            return
        if abs(self.change_x) > 0.05:
            self._animator.play(self._walk)
        else:
            self._animator.play(self._idle)
        self.texture = self._animator.update(delta_time)
        sprites.apply_facing(self, self.facing)
        self._tick_dash(delta_time)
        if self.is_dashing:
            self.change_x = self._dash_dir * settings.PLAYER_DASH_SPEED
        else:
            self._apply_horizontal(delta_time)
        self._physics.update()
        grounded = self._physics.can_jump()
        if grounded and not self._was_on_ground:
            self._landing_timer = settings.PLAYER_LANDING_SLOW_TIME
        self._was_on_ground = grounded
        if grounded:
            self._time_off_ground = 0.0
            self._landing_timer = max(0.0, self._landing_timer - delta_time)
        else:
            self._time_off_ground += delta_time
        self._update_trail(delta_time)

    def _update_trail(self, delta_time: float) -> None:
        if self.is_dashing:
            self._trail.append([self.center_x, self.center_y, settings.PLAYER_DASH_TRAIL_LIFE])
        alive: list[list[float]] = []
        for pos_x, pos_y, life in self._trail:
            remaining = life - delta_time
            if remaining > 0.0:
                alive.append([pos_x, pos_y, remaining])
        self._trail = alive[-18:]

    def _tick_dash(self, delta_time: float) -> None:
        if self._dash_timer > 0.0:
            self._dash_timer = max(0.0, self._dash_timer - delta_time)
            if self._dash_timer == 0.0:
                self.change_x = self._dash_dir * settings.PLAYER_SPEED
        was_cooling = self._dash_cooldown > 0.0
        if was_cooling:
            self._dash_cooldown = max(0.0, self._dash_cooldown - delta_time)
            if self._dash_cooldown == 0.0:
                self._ready_flash = settings.PLAYER_DASH_READY_FLASH
        if self._ready_flash > 0.0:
            self._ready_flash = max(0.0, self._ready_flash - delta_time)

    def _apply_horizontal(self, delta_time: float) -> None:
        grounded = self._was_on_ground
        landing = grounded and self._landing_timer > 0.0
        max_speed = settings.PLAYER_SPEED * (
            settings.PLAYER_LANDING_SPEED_SCALE if landing else 1.0
        )
        accel = max_speed / max(settings.PLAYER_ACCEL_TIME, 0.001)
        direction = self._move_dir
        if grounded:
            if direction == 0:
                self.change_x += (0.0 - self.change_x) * _exp_alpha(
                    delta_time, settings.PLAYER_SLIDE_TIME
                )
                if abs(self.change_x) < 0.18:
                    self.change_x = 0.0
                return
            if self.change_x * direction < 0.0:
                accel *= 1.55
            self.change_x = _approach(self.change_x, direction * max_speed, accel * delta_time)
            return
        if direction == 0:
            return
        air_accel = accel * settings.PLAYER_AIR_CONTROL
        self.change_x = _approach(
            self.change_x, direction * settings.PLAYER_SPEED, air_accel * delta_time
        )
