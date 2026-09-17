"""Boss golem : ennemi lourd a distance (projectile, laser, piques).

Priorites :
    1. DYING  : animation de mort, plus d'attaque ;
    2. SHOOT / LASER / SPIKES : attaque engagee jusqu'a la fin ;
    3. CHASE  : le joueur est a portee -> se tourne vers lui, recule pour
                garder la distance, puis arme l'attaque suivante du cycle ;
    4. PATROL : va-et-vient lent, demi-tour au mur ou au bord.

Le contact du corps ne tue pas : seuls le projectile (`BossShot`), le
laser (`laser_hits`) et la vague de piques sont mortels.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from enum import Enum, auto

from dataclasses import dataclass

import arcade

import settings
from src.entities.boss_death_fx import BossDeathFx
from src.entities.boss_spikes import BossSpikeWave
from src.entities.enemy_base import EnemyBase
from src.entities.item import Item, ItemKind
from src.entities.particles import LaserBurst
from src.entities.player import Player
from src.ui import sprites


class BossState(Enum):
    """Etats de l'IA."""

    PATROL = auto()
    CHASE = auto()
    SHOOT = auto()
    LASER = auto()
    SPIKES = auto()
    DYING = auto()


def _walk_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.SPRITE_BOSS_WALK,
        settings.BOSS_FRAME,
        settings.BOSS_FRAME,
        scale=settings.BOSS_SCALE,
    )
    return sprites.StripAnimation(frames, settings.ANIM_BOSS_WALK_FRAME_TIME, loop=True)


def _shot_animation() -> sprites.StripAnimation:
    frames = _visible_textures(
        sprites.load_grid(
            settings.SPRITE_BOSS_SHOT,
            settings.BOSS_FRAME,
            settings.BOSS_FRAME,
            scale=settings.BOSS_SCALE,
        )
    )
    return sprites.StripAnimation(frames, settings.ANIM_BOSS_SHOT_FRAME_TIME, loop=False)


def _linger_alternate(frames: tuple[arcade.Texture, ...], count: int) -> tuple[arcade.Texture, ...]:
    """Repete en alternance la derniere frame et l'avant-derniere."""
    if count <= 0:
        return ()
    last = frames[-1]
    previous = frames[-2] if len(frames) > 1 else last
    return tuple(last if index % 2 == 0 else previous for index in range(count))


def _laser_body_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.SPRITE_BOSS_LASER,
        settings.BOSS_FRAME,
        settings.BOSS_FRAME,
        scale=settings.BOSS_SCALE,
    )
    linger = _linger_alternate(frames, settings.BOSS_LASER_LINGER_FRAMES)
    return sprites.StripAnimation(
        frames + linger, settings.ANIM_BOSS_LASER_FRAME_TIME, loop=False
    )


def _death_animation() -> sprites.StripAnimation:
    frames = _visible_textures(
        sprites.load_grid(
            settings.SPRITE_BOSS_DEATH,
            settings.BOSS_DEATH_FRAME,
            settings.BOSS_DEATH_FRAME,
            scale=settings.BOSS_SCALE,
        )
    )
    return sprites.StripAnimation(frames, settings.ANIM_BOSS_DEATH_FRAME_TIME, loop=False)


def _projectile_frames() -> tuple[arcade.Texture, ...]:
    return sprites.load_strip(
        settings.SPRITE_BOSS_PROJECTILE,
        settings.BOSS_PROJECTILE_FRAME_WIDTH,
        settings.BOSS_PROJECTILE_FRAME_HEIGHT,
        scale=settings.BOSS_SCALE,
    )


def _beam_grid() -> tuple[arcade.Texture, ...]:
    return sprites.load_grid(
        settings.SPRITE_BOSS_BEAM,
        settings.BOSS_BEAM_FRAME_WIDTH,
        settings.BOSS_BEAM_FRAME_HEIGHT,
    )


def _visible_textures(frames: tuple[arcade.Texture, ...]) -> tuple[arcade.Texture, ...]:
    """Ignore les cellules vides d'une planche (alpha quasi nulle)."""
    visible: list[arcade.Texture] = []
    for texture in frames:
        image = getattr(texture, "image", None)
        if image is None:
            visible.append(texture)
            continue
        extrema = image.getextrema()
        if image.mode == "RGBA" and extrema[3][1] <= 8:
            continue
        visible.append(texture)
    return tuple(visible) if visible else frames


def _content_bottom_from_center(texture: arcade.Texture) -> float:
    """Distance du centre au pixel opaque le plus bas (vers le sol)."""
    image = getattr(texture, "image", None)
    height = float(texture.height)
    if image is None:
        return height / 2.0
    alpha = image.split()[-1] if image.mode == "RGBA" else None
    bbox = alpha.getbbox() if alpha is not None else image.getbbox()
    if bbox is None:
        return height / 2.0
    return float(bbox[3]) - height / 2.0


def _fade_beam_tip(texture: arcade.Texture, index: int) -> arcade.Texture:
    """Estompe le bord droit d'une frame de rayon (pointe vers le vide)."""
    image = getattr(texture, "image", None)
    if image is None:
        return texture
    ratio = settings.BOSS_LASER_TIP_FADE
    if ratio <= 0.0:
        return texture
    faded = image.convert("RGBA").copy()
    width, height = faded.size
    fade_px = max(1, int(round(width * min(1.0, ratio))))
    start = width - fade_px
    pixels = faded.load()
    for column in range(start, width):
        progress = (column - start + 1) / fade_px
        factor = (1.0 - progress) * (1.0 - progress)
        for row in range(height):
            red, green, blue, alpha = pixels[column, row]
            if alpha:
                pixels[column, row] = (red, green, blue, int(alpha * factor))
    return arcade.Texture(
        faded, hash=f"boss-beam-tip|{index}|{ratio:.3f}|{width}x{height}"
    )


def _beam_frame_info(texture: arcade.Texture) -> tuple[float, bool]:
    """Ancre X du contenu et si la frame est un rayon etire."""
    image = getattr(texture, "image", None)
    if image is None:
        return settings.BOSS_BEAM_FRAME_WIDTH * 0.13, True
    alpha = image.split()[-1] if image.mode == "RGBA" else None
    bbox = alpha.getbbox() if alpha is not None else image.getbbox()
    if bbox is None:
        return settings.BOSS_BEAM_FRAME_WIDTH * 0.13, True
    left, _top, right, _bottom = bbox
    full = (right - left) >= settings.BOSS_BEAM_FULL_MIN_WIDTH
    return float(left), full


@dataclass(frozen=True, slots=True)
class _BeamStrip:
    animation: sprites.StripAnimation
    anchors: tuple[float, ...]
    full: tuple[bool, ...]


def _beam_strip() -> _BeamStrip:
    """Toutes les frames visibles de Laser_sheet, dans l'ordre, puis linger."""
    visible = _visible_textures(_beam_grid())
    anchors = []
    full_flags = []
    faded: list[arcade.Texture] = []
    for index, texture in enumerate(visible):
        anchor, full = _beam_frame_info(texture)
        anchors.append(anchor)
        full_flags.append(full)
        faded.append(_fade_beam_tip(texture, index) if full else texture)
    linger_tex = _linger_alternate(tuple(faded), settings.BOSS_LASER_LINGER_FRAMES)
    linger_idx = [
        (len(visible) - 1) if index % 2 == 0 else max(0, len(visible) - 2)
        for index in range(settings.BOSS_LASER_LINGER_FRAMES)
    ]
    textures = tuple(faded) + linger_tex
    all_anchors = tuple(anchors) + tuple(anchors[i] for i in linger_idx)
    all_full = tuple(full_flags) + tuple(full_flags[i] for i in linger_idx)
    return _BeamStrip(
        sprites.StripAnimation(textures, settings.ANIM_BOSS_BEAM_FRAME_TIME, loop=False),
        all_anchors,
        all_full,
    )


def _closest_on_segment(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> tuple[float, float]:
    """Projection de (px, py) sur le segment AB, bornee aux extremites."""
    abx = bx - ax
    aby = by - ay
    length2 = abx * abx + aby * aby
    if length2 <= 1e-6:
        return ax, ay
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / length2))
    return ax + abx * t, ay + aby * t


def _capsule_hits_aabb(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    radius: float,
    left: float,
    right: float,
    bottom: float,
    top: float,
) -> bool:
    """Le segment epaissi touche-t-il le rectangle ?"""
    mid_x = (left + right) * 0.5
    mid_y = (bottom + top) * 0.5
    qx, qy = _closest_on_segment(mid_x, mid_y, ax, ay, bx, by)
    closest_x = max(left, min(right, qx))
    closest_y = max(bottom, min(top, qy))
    dx = closest_x - qx
    dy = closest_y - qy
    return dx * dx + dy * dy <= radius * radius


def _wrap_deg(delta: float) -> float:
    """Ramene un angle en degres dans ]-180, 180]."""
    return (delta + 180.0) % 360.0 - 180.0


def _smooth_damp_angle(
    current: float,
    target: float,
    velocity: float,
    smooth_time: float,
    delta_time: float,
    max_speed: float = 0.0,
) -> tuple[float, float]:
    """Visee inertielle (courbe SmoothDamp), pas un suivi retarde."""
    dt = max(delta_time, 1e-6)
    smooth = max(smooth_time, 1e-4)
    omega = 2.0 / smooth
    x = omega * dt
    exp = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)
    change = _wrap_deg(current - target)
    if max_speed > 0.0:
        max_change = max_speed * smooth
        if change > max_change:
            change = max_change
        elif change < -max_change:
            change = -max_change
    original_to = current - change
    temp = (velocity + omega * change) * dt
    new_velocity = (velocity - omega * temp) * exp
    output = original_to + (change + temp) * exp
    # Evite le depassement, dans l'espace deroule (pas d'angle wrap ici).
    if (original_to - current > 0.0) == (output > original_to):
        output = original_to
        new_velocity = 0.0
    return output, new_velocity


class BossShot(arcade.Sprite):
    """Bras-projectile lance par le boss, mortel au contact."""

    lethal = True

    def __init__(
        self,
        center_x: float,
        center_y: float,
        target_x: float,
        target_y: float,
        walls: Sequence[arcade.SpriteList],
        burst: LaserBurst | None = None,
        jitter_deg: float | None = None,
    ) -> None:
        frames = _projectile_frames()
        super().__init__(frames[0], center_x=center_x, center_y=center_y)
        sprites.apply_rect_hit_box(self, settings.BOSS_SHOT_WIDTH, settings.BOSS_SHOT_HEIGHT)
        self._animator = sprites.Animator(
            sprites.StripAnimation(frames, settings.ANIM_BOSS_PROJECTILE_FRAME_TIME, loop=True)
        )
        dx = target_x - center_x
        dy = target_y - center_y
        angle = math.atan2(dy, dx)
        spread = settings.BOSS_SHOT_SPREAD_DEG if jitter_deg is None else jitter_deg
        if spread:
            angle += math.radians(random.uniform(-spread, spread))
        self._dir_x = math.cos(angle)
        self._dir_y = math.sin(angle)
        speed = settings.BOSS_SHOT_SPEED
        self.change_x = self._dir_x * speed
        self.change_y = self._dir_y * speed
        # Art oriente vers la gauche. Arcade.angle est horaire, atan2 anti-horaire.
        self._flight_angle = settings.BOSS_SHOT_ART_ANGLE - math.degrees(angle)
        self.angle = self._flight_angle
        self._walls = list(walls)
        self._burst = burst
        self._max_life = settings.BOSS_SHOT_LIFE
        self._life = self._max_life

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        dt = max(0.0, delta_time)
        self._life -= dt
        age = 1.0 - max(0.0, self._life) / self._max_life
        ease = 1.0 - (1.0 - min(1.0, age)) ** 3
        speed = (
            settings.BOSS_SHOT_SPEED
            + (settings.BOSS_SHOT_SPEED_END - settings.BOSS_SHOT_SPEED) * ease
        )
        self.change_x = self._dir_x * speed
        self.change_y = self._dir_y * speed
        self.center_x += self.change_x
        self.center_y += self.change_y
        self.texture = self._animator.update(dt)
        self.angle = self._flight_angle
        if self._hits_wall():
            self._explode()
            return
        if self._life <= 0.0:
            self.remove_from_sprite_lists()

    def _hits_wall(self) -> bool:
        return any(
            arcade.check_for_collision_with_list(self, walls) for walls in self._walls if walls
        )

    def _explode(self) -> None:
        if self._burst is not None:
            self._burst.emit(self.center_x, self.center_y)
        self.remove_from_sprite_lists()


class Boss(EnemyBase):
    """Golem de pierre : patrouille, puis projectile ou laser."""

    def __init__(self, center_x: float, center_y: float) -> None:
        self._walk = _walk_animation()
        self._shoot = _shot_animation()
        self._laser_anim = _laser_body_animation()
        self._die = _death_animation()
        super().__init__(
            self._walk.textures[0],
            center_x=center_x,
            center_y=center_y,
            hit_points=settings.BOSS_HIT_POINTS,
            body_width=settings.BOSS_WIDTH,
            body_height=settings.BOSS_HEIGHT,
        )
        sprites.apply_rect_hit_box(
            self,
            settings.BOSS_WIDTH,
            settings.BOSS_HEIGHT,
            offset_y=settings.BOSS_HITBOX_OFFSET_Y,
        )
        self._animator = sprites.Animator(self._walk)
        self.state = BossState.PATROL
        self.facing = -1
        sprites.apply_facing(self, self.facing)
        self.attack_reach = 0.0
        self.attack_vertical_range = settings.BOSS_AGGRO_VERTICAL_RANGE
        self._attack_cooldown = 0.0
        self._attack_index = 0
        self._shot_spawned = False
        self._fire_sound_pending = False
        self._death_ground_y: float | None = None
        self.shots = arcade.SpriteList()
        self._shot_burst = LaserBurst()
        self._spike_wave = BossSpikeWave()
        self._death_fx = BossDeathFx()
        self._beam_strip = _beam_strip()
        self._beam = arcade.Sprite(self._beam_strip.animation.textures[0])
        self._beam_anim = sprites.Animator(self._beam_strip.animation)
        self._laser_dir_x = -1.0
        self._laser_dir_y = 0.0
        self._aim_angle = 180.0
        self._aim_angle_vel = 0.0
        self._physics: arcade.PhysicsEnginePlatformer | None = None
        self._platforms: list[arcade.SpriteList] = []
        self._configure_glow(
            scale=settings.BOSS_GHOST_GLOW_SCALE,
            alpha=settings.BOSS_GHOST_GLOW_ALPHA,
            inner_scale=settings.BOSS_GHOST_GLOW_INNER_SCALE,
            inner_alpha=settings.BOSS_GHOST_GLOW_INNER_ALPHA,
            pulse=settings.BOSS_GHOST_GLOW_PULSE,
            pulse_speed=settings.BOSS_GHOST_GLOW_PULSE_SPEED,
            color=settings.COLOR_BOSS_GLOW,
            color_core=settings.COLOR_BOSS_GLOW_CORE,
        )

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(
        self,
        platforms: Sequence[arcade.SpriteList],
        hazards: arcade.SpriteList | None = None,
    ) -> None:
        del hazards
        self._platforms = list(platforms)
        self._physics = arcade.PhysicsEnginePlatformer(
            self,
            walls=self._platforms,
            gravity_constant=settings.GRAVITY,
        )

    # ------------------------------------------------------------------ #
    # Attaque
    # ------------------------------------------------------------------ #

    @property
    def strike_active(self) -> bool:
        """Le corps du boss ne tue pas au contact."""
        return False

    @property
    def laser_active(self) -> bool:
        if self.state is not BossState.LASER:
            return False
        if self._beam_fade() <= 0.2:
            return False
        index = min(self._beam_anim.frame_index, len(self._beam_strip.full) - 1)
        return self._beam_strip.full[index]

    def _beam_fade(self) -> float:
        """1 = opaque, 0 = disparu. Fondu sur les dernieres fractions de seconde."""
        fade_time = settings.BOSS_LASER_FADE_TIME
        animation = self._beam_anim.animation
        duration = animation.frame_time * len(animation.textures)
        remaining = max(0.0, (duration - self._beam_anim.elapsed) / self._beam_anim.speed)
        if remaining >= fade_time:
            return 1.0
        return remaining / fade_time

    def _laser_charge_timescale(self) -> float:
        """Ralentit les premieres etincelles, puis reprend le rythme normal."""
        if self.laser_active:
            return 1.0
        slow_frames = settings.BOSS_LASER_CHARGE_SLOW_FRAMES
        if slow_frames <= 0 or self._beam_anim.frame_index >= slow_frames:
            return 1.0
        natural = (
            slow_frames
            * self._beam_strip.animation.frame_time
            / max(self._beam_anim.speed, 0.001)
        )
        target = max(settings.BOSS_LASER_CHARGE_SLOW_TIME, 0.001)
        return natural / target

    def _laser_origin(self) -> tuple[float, float]:
        """Gemme frontale, source du rayon."""
        return (
            self.center_x + self.facing * settings.BOSS_LASER_ORIGIN_X,
            self.center_y + settings.BOSS_LASER_ORIGIN_Y,
        )

    def _aim_laser(self, player: Player | None, delta_time: float = 0.0, *, snap: bool = False) -> None:
        """Pointe le rayon avec une courbe d'inertie, pas un suivi aveugle."""
        origin_x, origin_y = self._laser_origin()
        if player is None or not player.alive:
            target = 0.0 if self.facing >= 0 else 180.0
        else:
            target = math.degrees(
                math.atan2(player.center_y - origin_y, player.center_x - origin_x)
            )
        if snap or settings.BOSS_LASER_SMOOTH_TIME <= 0.0:
            self._aim_angle = target
            self._aim_angle_vel = 0.0
        else:
            self._aim_angle, self._aim_angle_vel = _smooth_damp_angle(
                self._aim_angle,
                target,
                self._aim_angle_vel,
                settings.BOSS_LASER_SMOOTH_TIME,
                delta_time,
                settings.BOSS_LASER_MAX_TURN_SPEED,
            )
        rad = math.radians(self._aim_angle)
        self._laser_dir_x = math.cos(rad)
        self._laser_dir_y = math.sin(rad)
        if abs(self._laser_dir_x) > 0.05:
            self.facing = 1 if self._laser_dir_x > 0 else -1

    def laser_bounds(self) -> tuple[float, float, float, float]:
        origin_x, origin_y = self._laser_origin()
        length = settings.BOSS_LASER_RANGE
        end_x = origin_x + self._laser_dir_x * length
        end_y = origin_y + self._laser_dir_y * length
        half = settings.BOSS_LASER_HEIGHT / 2
        return (
            min(origin_x, end_x) - half,
            max(origin_x, end_x) + half,
            min(origin_y, end_y) - half,
            max(origin_y, end_y) + half,
        )

    def laser_hits(self, target: arcade.Sprite) -> bool:
        if not self.laser_active:
            return False
        origin_x, origin_y = self._laser_origin()
        length = settings.BOSS_LASER_RANGE
        return _capsule_hits_aabb(
            origin_x,
            origin_y,
            origin_x + self._laser_dir_x * length,
            origin_y + self._laser_dir_y * length,
            settings.BOSS_LASER_HEIGHT / 2,
            target.left,
            target.right,
            target.bottom,
            target.top,
        )

    def spike_hits(self, target: arcade.Sprite) -> bool:
        return self._spike_wave.hits(target)

    # ------------------------------------------------------------------ #
    # Mort
    # ------------------------------------------------------------------ #

    def _death_drop(self) -> Item:
        """Le boss laisse la cle du niveau, pas la bille bleue habituelle."""
        return Item(ItemKind.KEY, self.center_x, self.center_y)

    def _on_death(self) -> None:
        self._death_ground_y = (
            self.center_y
            - _content_bottom_from_center(self.texture)
            + settings.BOSS_DEATH_GROUND_OFFSET_Y
        )
        self.state = BossState.DYING
        self.change_x = 0.0
        self._clear_shots()
        self._spike_wave.clear()
        self._animator.play(self._die, restart=True)
        self.texture = self._die.textures[0]
        sprites.apply_facing(self, self.facing)
        self._pin_death_to_ground()
        self._death_fx.start(self.center_x, self.center_y)

    def _on_respawn(self) -> None:
        self.state = BossState.PATROL
        self._attack_cooldown = 0.0
        self._attack_index = 0
        self._shot_spawned = False
        self._fire_sound_pending = False
        self._clear_shots()
        self._spike_wave.clear()
        self._death_fx.clear()
        self._death_ground_y = None
        self.visible = True
        self.facing = -1
        self._animator.play(self._walk, restart=True)
        self.texture = self._walk.textures[0]
        sprites.apply_facing(self, self.facing)

    def _pin_death_to_ground(self) -> None:
        """Garde les pieds sur la ligne du sol : l'enfouissement se joue dans la frame."""
        if self._death_ground_y is None:
            return
        self.center_y = self._death_ground_y + _content_bottom_from_center(self.texture)

    def _clear_shots(self) -> None:
        for shot in list(self.shots):
            shot.remove_from_sprite_lists()

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(
        self,
        delta_time: float = settings.FRAME_TIME,
        *args,
        player: Player | None = None,
        corpses: arcade.SpriteList | None = None,
        **kwargs,
    ) -> None:
        del corpses
        dt = max(0.0, delta_time)
        self._tick_hit_feedback(dt)
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        self.shots.update(dt)
        self._shot_burst.update(dt)
        self._spike_wave.update(dt)
        self._death_fx.update(self.center_x, self.center_y, dt)
        if self.state is BossState.DYING:
            self.change_x = self._knockback_x
            self._knockback_x *= settings.ENEMY_KNOCKBACK_FRICTION
        elif self.state is BossState.SHOOT:
            self.change_x = 0.0
            self._tick_shoot(player)
        elif self.state is BossState.LASER:
            self.change_x = 0.0
        elif self.state is BossState.SPIKES:
            self.change_x = 0.0
            if self._spike_wave.finished:
                self._spike_wave.clear()
                self._end_attack()
        elif self._player_in_range(player):
            self._chase(player)
        else:
            self._patrol()
        self._advance_animation(dt)
        if self.state is BossState.LASER:
            self._aim_laser(player, dt)
            sprites.apply_facing(self, self.facing)
            self._layout_beam()
        if (
            self.state is BossState.LASER
            and self._animator.finished
            and self._beam_anim.finished
        ):
            self._end_attack()
        if self._physics is not None:
            self._physics.update()
        if self.state is BossState.DYING:
            self._pin_death_to_ground()
        if self.state is BossState.DYING and self._animator.finished:
            self.visible = False
            if not self._death_fx.active:
                self._clear_shots()
                self._spike_wave.clear()
                self._death_fx.clear()
                self.remove_from_sprite_lists()

    def draw_attacks(self) -> None:
        """Projectiles, eclat, piques et rayon, au-dessus du corps du boss."""
        self.shots.draw(pixelated=True)
        self._shot_burst.draw()
        self._spike_wave.draw()
        self._death_fx.draw()
        if self.state is not BossState.LASER:
            return
        self._layout_beam()
        sprites.draw_pixel_sprite(self._beam)

    def _layout_beam(self) -> None:
        """Place le sprite du rayon : source sur la gemme, oriente vers la cible."""
        frames = self._beam_anim.animation.textures
        index = min(self._beam_anim.frame_index, len(frames) - 1)
        self._beam.texture = frames[index]
        scale = settings.BOSS_SCALE
        tex_width = max(1.0, float(self._beam.texture.width))
        anchor = self._beam_strip.anchors[index]
        full = self._beam_strip.full[index]
        if full:
            width = settings.BOSS_LASER_RANGE
            inset = anchor * (width / tex_width)
        else:
            width = tex_width * scale
            inset = anchor * scale
        self._beam.width = width
        self._beam.scale_y = scale
        if self._beam.scale_x < 0.0:
            self._beam.scale_x = abs(self._beam.scale_x)
        angle = -math.degrees(math.atan2(self._laser_dir_y, self._laser_dir_x))
        self._beam.angle = angle
        along = width / 2.0 - inset
        art = settings.BOSS_LASER_ORIGIN_Y
        theta = math.radians(angle)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        origin_x, origin_y = self._laser_origin()
        self._beam.center_x = origin_x + along * cos_t - art * sin_t
        self._beam.center_y = origin_y - along * sin_t - art * cos_t
        self._beam.alpha = max(0, min(255, int(255 * self._beam_fade())))

    # ------------------------------------------------------------------ #
    # Comportements
    # ------------------------------------------------------------------ #

    def _player_in_range(self, player: Player | None) -> bool:
        if player is None or not player.alive:
            return False
        if abs(player.center_y - self.center_y) > settings.BOSS_AGGRO_VERTICAL_RANGE:
            return False
        return arcade.get_distance_between_sprites(self, player) <= settings.BOSS_AGGRO_RANGE

    def _chase(self, player: Player) -> None:
        self.state = BossState.CHASE
        self.facing = 1 if player.center_x >= self.center_x else -1
        gap = abs(player.center_x - self.center_x)
        if self._attack_cooldown <= 0.0:
            self._start_attack(player)
            return
        if gap < settings.BOSS_PREFERRED_DISTANCE:
            self._walk_direction(-self.facing)
        else:
            self.change_x = 0.0

    def _start_attack(self, player: Player) -> None:
        attack = self._attack_index % 3
        self._attack_index += 1
        if attack == 1 and not self._laser_has_line(player):
            attack = 0
        if attack == 1:
            self.state = BossState.LASER
            self._aim_laser(player, snap=True)
            self._animator.play(self._laser_anim, restart=True)
            self._beam_anim.play(self._beam_strip.animation, restart=True)
            self._beam.alpha = 255
            self._layout_beam()
        elif attack == 2:
            self.state = BossState.SPIKES
            self._spike_wave.start(
                self.center_x,
                self.bottom + settings.BOSS_SPIKE_SIZE / 2.0,
                player.center_x,
                self._platforms,
            )
            self._animator.play(self._walk, restart=True)
        else:
            self.state = BossState.SHOOT
            self._shot_spawned = False
            self._animator.play(self._shoot, restart=True)
        self.change_x = 0.0

    def _tick_shoot(self, player: Player | None) -> None:
        if (
            not self._shot_spawned
            and self._animator.frame_index >= settings.BOSS_SHOT_SPAWN_FRAME
        ):
            self._spawn_shot(player)
        if self._animator.finished:
            self._end_attack()

    def _spawn_shot(self, player: Player | None, jitter_deg: float | None = None) -> None:
        self._shot_spawned = True
        self._fire_sound_pending = True
        origin_x = self.center_x + self.facing * settings.BOSS_SHOT_ORIGIN_X
        origin_y = self.center_y + settings.BOSS_SHOT_ORIGIN_Y
        if player is not None:
            target_x, target_y = player.center_x, player.center_y
        else:
            target_x = origin_x + self.facing * 120.0
            target_y = origin_y
        shot = BossShot(
            origin_x,
            origin_y,
            target_x,
            target_y,
            self._platforms,
            burst=self._shot_burst,
            jitter_deg=jitter_deg,
        )
        self.shots.append(shot)

    def consume_fire_sound(self) -> bool:
        """True si un projectile vient d'etre lance depuis la derniere lecture."""
        pending = self._fire_sound_pending
        self._fire_sound_pending = False
        return pending

    def consume_death_shakes(self) -> list[tuple[float, float]]:
        """Secousses camera enfilees par les booms de mort."""
        return self._death_fx.consume_shakes()

    def _end_attack(self) -> None:
        self.state = BossState.CHASE
        self._attack_cooldown = settings.BOSS_ATTACK_COOLDOWN
        self._shot_spawned = False

    def _laser_has_line(self, player: Player) -> bool:
        origin_x, origin_y = self._laser_origin()
        reach = math.hypot(player.center_x - origin_x, player.center_y - origin_y)
        return reach <= settings.BOSS_LASER_RANGE

    def _patrol(self) -> None:
        self.state = BossState.PATROL
        if self._blocked_ahead() or not self._floor_ahead():
            self.facing = -self.facing
        self.change_x = self.facing * settings.BOSS_PATROL_SPEED

    def _walk_direction(self, direction: int) -> None:
        self.facing = 1 if direction >= 0 else -1
        if self._blocked_ahead() or not self._floor_ahead():
            self.change_x = 0.0
            return
        self.change_x = self.facing * settings.BOSS_PATROL_SPEED

    def _blocked_ahead(self) -> bool:
        probe = (self.center_x + self.facing * (settings.BOSS_WIDTH / 2 + 4), self.center_y)
        return self._solid_at(probe)

    def _floor_ahead(self) -> bool:
        if not self._platforms:
            return True
        probe = (self.center_x + self.facing * (settings.BOSS_WIDTH / 2 + 4), self.bottom - 4)
        return self._solid_at(probe)

    def _solid_at(self, point: tuple[float, float]) -> bool:
        return any(arcade.get_sprites_at_point(point, walls) for walls in self._platforms)

    def _advance_animation(self, delta_time: float) -> None:
        if self.state is BossState.DYING:
            self._animator.play(self._die)
        elif self.state is BossState.SHOOT:
            self._animator.play(self._shoot)
        elif self.state is BossState.LASER:
            self._animator.play(self._laser_anim)
        elif self.state is BossState.SPIKES:
            self._animator.play(self._walk)
        elif abs(self.change_x) <= 0.05:
            self._animator.play(self._walk)
        else:
            self._animator.play(self._walk)
        self.texture = self._animator.update(delta_time)
        sprites.apply_facing(self, self.facing)
        if self.state is BossState.LASER:
            self._beam_anim.update(delta_time * self._laser_charge_timescale())

