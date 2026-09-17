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
from src.entities.particles import DustParticles
from src.entities.trail import PointTrail
from src.ui import sprites


def _idle_frames() -> tuple[arcade.Texture, ...]:
    return sprites.load_strip(
        settings.SPRITE_PLAYER_IDLE,
        settings.SPRITE_FRAME_SIZE,
        scale=settings.ENTITY_SCALE,
    )


def _idle_still_animation(frames: tuple[arcade.Texture, ...]) -> sprites.StripAnimation:
    """Pose figee : premiere frame, sans respiration."""
    return sprites.StripAnimation((frames[0],), settings.ANIM_IDLE_FRAME_TIME, loop=True)


def _idle_breathe_animation(frames: tuple[arcade.Texture, ...]) -> sprites.StripAnimation:
    """Idle qui respire, reserve au cooldown du dash."""
    return sprites.StripAnimation(frames, settings.ANIM_IDLE_FRAME_TIME, loop=True)


def _walk_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.SPRITE_PLAYER_WALK,
        settings.SPRITE_FRAME_SIZE,
        scale=settings.ENTITY_SCALE,
    )
    return sprites.StripAnimation(frames, settings.ANIM_WALK_FRAME_TIME, loop=True)


def _attack_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.SPRITE_PLAYER_ATTACK,
        settings.SPRITE_FRAME_SIZE,
        scale=settings.ENTITY_SCALE,
    )
    return sprites.StripAnimation(frames, settings.ANIM_PLAYER_ATTACK_FRAME_TIME, loop=False)


def _death_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.SPRITE_PLAYER_DEATH,
        settings.SPRITE_FRAME_SIZE,
        scale=settings.ENTITY_SCALE,
    )
    # Frame du milieu : chute. La derniere (corps au sol) est le cadavre.
    fall = frames[len(frames) // 2]
    return sprites.StripAnimation(
        (fall, frames[-1]),
        settings.ANIM_PLAYER_DEATH_FRAME_TIME,
        loop=False,
    )


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


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
        idle_frames = _idle_frames()
        self._idle_still = _idle_still_animation(idle_frames)
        self._idle_breathe = _idle_breathe_animation(idle_frames)
        self._walk = _walk_animation()
        self._attack = _attack_animation()
        self._death = _death_animation()
        super().__init__(self._idle_still.textures[0], center_x=center_x, center_y=center_y)
        sprites.apply_rect_hit_box(
            self,
            settings.PLAYER_HITBOX_WIDTH * settings.ENTITY_SCALE,
            settings.PLAYER_HEIGHT * settings.ENTITY_SCALE,
        )
        self._animator = sprites.Animator(self._idle_still)
        self._attack_animator = sprites.Animator(self._attack, speed=1.0)
        self.alive = True
        self.facing = 1
        self.inventory: set[ItemKind] = set()
        self.respawn_point: tuple[float, float] = (center_x, center_y)
        self._physics: arcade.PhysicsEnginePlatformer | None = None
        self._solids: list[arcade.SpriteList] = []
        self._time_off_ground = 0.0
        self._place_on_tile(center_x, center_y)
        self._was_on_ground = True
        self._jump_held = False
        self._jump_buffer = 0.0
        self._move_dir = 0
        self._landing_timer = 0.0
        self._dash_timer = 0.0
        self._dash_dir = 1
        self._dash_cooldown = 0.0
        self._dash_from_ground = False
        self._dash_jump = False
        self._ready_flash = 0.0
        self._dust = DustParticles()
        self._dash_trail = PointTrail(
            settings.COLOR_TRAIL_DASH,
            settings.COLOR_TRAIL_DASH_CORE,
        )
        self._attack_time_left = 0.0
        self._attack_cooldown_left = 0.0
        self._attack_hit_targets: set[int] = set()
        self._attack_stage = 0
        self._attack_chain_timer = 0.0
        self._attack_queued = False
        self._attack_sound_events: list[int] = []
        self._attack_sound_played = False
        self._footstep_events: list[str] = []
        self._footstep_timer = 0.0
        self._jump_sound_pending = False
        self._death_elapsed = 0.0

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
        self._solids = list(walls)
        if platforms:
            self._solids.extend(platforms)

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
    def is_high_speed(self) -> bool:
        """True tant que la vitesse horizontale reste proche d'un dash."""
        return abs(self.change_x) >= settings.PLAYER_DASH_SPEED * settings.PARTICLE_HIGH_SPEED_RATIO

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

    @property
    def is_attacking(self) -> bool:
        """Indique si la hitbox de l'attaque est actuellement active."""
        return self.alive and self._attack_time_left > 0.0

    @property
    def attack_cooldown_left(self) -> float:
        """Retourne le temps restant avant de pouvoir frapper a nouveau."""
        return max(0.0, self._attack_cooldown_left)

    @property
    def attack_progress(self) -> float:
        """Retourne l'avancement de la frappe entre 0.0 et 1.0."""
        duration = self.attack_duration
        if not self.is_attacking or duration <= 0.0:
            return 1.0
        return 1.0 - self._attack_time_left / duration

    @property
    def attack_stage(self) -> int:
        """Numero du coup actuellement joue, ou 0 hors animation."""
        return self._attack_stage if self.is_attacking else 0

    @property
    def attack_queued(self) -> bool:
        """Indique si le prochain coup du combo a ete demande."""
        return self.is_attacking and self._attack_queued

    @property
    def attack_impact_active(self) -> bool:
        """Vrai quand la frame visible de la lame peut toucher une cible."""
        return self.is_attacking and self.attack_progress >= settings.PLAYER_ATTACK_IMPACT_PROGRESS

    @property
    def attack_duration(self) -> float:
        """Duree du coup actif, adaptee a son rang dans le combo."""
        return self._stage_value(settings.PLAYER_ATTACK_DURATIONS, settings.PLAYER_ATTACK_DURATION)

    @property
    def attack_range(self) -> float:
        """Portee horizontale du coup actif."""
        return self._stage_value(settings.PLAYER_ATTACK_RANGES, settings.PLAYER_ATTACK_RANGE)

    @property
    def attack_damage(self) -> int:
        """Degats du coup actif."""
        return int(self._stage_value(settings.PLAYER_ATTACK_DAMAGES, settings.PLAYER_ATTACK_DAMAGE))

    @property
    def attack_knockback_scale(self) -> float:
        """Multiplicateur de recul du coup actif."""
        return self._stage_value(settings.PLAYER_ATTACK_KNOCKBACK_SCALES, 1.0)

    @property
    def attack_vertical_scale(self) -> float:
        """Hauteur relative de la hitbox du coup actif."""
        return self._stage_value(settings.PLAYER_ATTACK_VERTICAL_SCALES, 1.0)

    @property
    def attack_bounds(self) -> tuple[float, float, float, float] | None:
        """Retourne la hitbox rectangulaire devant le joueur, si elle est active."""
        if not self.attack_impact_active:
            return None
        if self.facing >= 0:
            left = self.right
            right = self.right + self.attack_range
        else:
            left = self.left - self.attack_range
            right = self.left
        half_height = abs(self.height) * 0.4 * self.attack_vertical_scale
        return left, self.center_y - half_height, right, self.center_y + half_height

    def has_item(self, kind: ItemKind) -> bool:
        return kind in self.inventory

    def give_item(self, kind: ItemKind) -> None:
        self.inventory.add(kind)

    def die(self) -> None:
        """Marque le corps comme mort, l'immobilise et lance l'anim de chute."""
        self.alive = False
        self.change_x = 0.0
        self.change_y = 0.0
        self._move_dir = 0
        self._jump_held = False
        self._jump_buffer = 0.0
        self._dash_timer = 0.0
        self._dash_from_ground = False
        self._dash_jump = False
        self._landing_timer = 0.0
        self._dust.clear()
        self._dash_trail.clear()
        self._attack_time_left = 0.0
        self._attack_hit_targets.clear()
        self._attack_stage = 0
        self._attack_chain_timer = 0.0
        self._attack_queued = False
        self._attack_sound_events.clear()
        self._attack_sound_played = False
        self._footstep_events.clear()
        self._footstep_timer = 0.0
        self._jump_sound_pending = False
        self._death_elapsed = 0.0
        self._animator.play(self._death, restart=True)
        self.texture = self._death.textures[0]
        sprites.apply_facing(self, self.facing)

    @property
    def death_settle_ratio(self) -> float:
        """0 = chute, 1 = corps au sol (apres le fondu)."""
        if self.alive:
            return 0.0
        hold = settings.ANIM_PLAYER_DEATH_FRAME_TIME
        blend = settings.ANIM_PLAYER_DEATH_BLEND_TIME
        if self._death_elapsed <= hold:
            return 0.0
        if blend <= 0.0:
            return 1.0
        return min(1.0, (self._death_elapsed - hold) / blend)

    @property
    def death_settled(self) -> bool:
        return not self.alive and self.death_settle_ratio >= 1.0

    def draw_sprite(self, fade: float = 1.0) -> None:
        """Dessine le corps, avec un petit fondu entre les poses de mort."""
        fade = max(0.0, min(1.0, fade))
        if fade <= 0.0:
            return
        if self.alive or self.death_settle_ratio <= 0.0:
            self.alpha = int(255 * fade)
            sprites.draw_pixel_sprite(self)
            self.alpha = 255
            return
        blend = _smoothstep(self.death_settle_ratio)
        if blend >= 1.0:
            return
        fall, lie = self._death.textures[0], self._death.textures[-1]
        saved = self.texture
        self.texture = fall
        sprites.apply_facing(self, self.facing)
        self.alpha = int(255 * fade * (1.0 - blend))
        if self.alpha > 0:
            sprites.draw_pixel_sprite(self)
        self.texture = lie
        sprites.apply_facing(self, self.facing)
        self.alpha = int(255 * fade * blend)
        if self.alpha > 0:
            sprites.draw_pixel_sprite(self)
        self.texture = saved
        sprites.apply_facing(self, self.facing)
        self.alpha = 255

    def respawn_at(self, position: tuple[float, float]) -> None:
        """Fait reapparaitre le corps au checkpoint fourni."""
        self.alive = True
        self._place_on_tile(*position)
        self.change_x = 0.0
        self.change_y = 0.0
        self._time_off_ground = 0.0
        self._was_on_ground = True
        self._jump_held = False
        self._jump_buffer = 0.0
        self._move_dir = 0
        self._landing_timer = 0.0
        self._dash_timer = 0.0
        self._dash_cooldown = 0.0
        self._dash_from_ground = False
        self._dash_jump = False
        self._ready_flash = 0.0
        self._dust.clear()
        self._dash_trail.clear()
        self._attack_time_left = 0.0
        self._attack_cooldown_left = 0.0
        self._attack_hit_targets.clear()
        self._attack_stage = 0
        self._attack_chain_timer = 0.0
        self._attack_queued = False
        self._attack_sound_events.clear()
        self._attack_sound_played = False
        self._footstep_events.clear()
        self._footstep_timer = 0.0
        self._jump_sound_pending = False
        self._death_elapsed = 0.0
        self._animator.play(self._idle_still, restart=True)
        self.texture = self._idle_still.textures[0]
        sprites.apply_facing(self, self.facing)

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
        self._dash_from_ground = self._time_off_ground <= settings.PLAYER_COYOTE_TIME
        self._dash_jump = False
        self._dash_timer = settings.PLAYER_DASH_DURATION
        self._dash_cooldown = settings.PLAYER_DASH_COOLDOWN
        self._ready_flash = 0.0
        self.change_x = self._dash_dir * settings.PLAYER_DASH_SPEED
        if self._dash_from_ground and self._jump_held and self._can_start_jump():
            self._start_jump()
        return True

    def jump(self) -> bool:
        """Tente un saut, ou le met en buffer si on est encore en l'air."""
        if not self.alive or self._physics is None:
            return False
        self._jump_held = True
        if self._can_start_jump():
            self._start_jump()
            return True
        self._jump_buffer = settings.PLAYER_JUMP_BUFFER
        return False

    def attack(self) -> bool:
        """Lance un coup ou memorise l'appui pour enchainer le suivant."""
        if not self.alive:
            return False
        if self.is_attacking:
            if (
                self._attack_stage < settings.PLAYER_ATTACK_COMBO_COUNT
                and self.attack_progress >= settings.PLAYER_ATTACK_BUFFER_PROGRESS
            ):
                self._attack_queued = True
                return True
            return False
        if self._attack_cooldown_left > 0.0:
            return False
        self._start_attack(self._next_attack_stage())
        return True

    def consume_footstep_events(self) -> tuple[str, ...]:
        """Pas et atterrissages depuis la derniere lecture."""
        events = tuple(self._footstep_events)
        self._footstep_events.clear()
        return events

    def consume_jump_sound(self) -> bool:
        """True si un saut a vraiment demarre depuis la derniere lecture."""
        pending = self._jump_sound_pending
        self._jump_sound_pending = False
        return pending

    def consume_attack_sound_events(self) -> tuple[int, ...]:
        """Retourne les impacts sonores depuis la derniere lecture."""
        events = tuple(self._attack_sound_events)
        self._attack_sound_events.clear()
        return events

    def attack_has_hit(self, target: object) -> bool:
        """Indique si la frappe en cours a deja touche cette cible."""
        return id(target) in self._attack_hit_targets

    def mark_attack_hit(self, target: object) -> None:
        """Enregistre une cible pour eviter les degats multiples d'une frappe."""
        self._attack_hit_targets.add(id(target))

    def _stage_value(self, values: Sequence[float | int], fallback: float | int) -> float:
        if not values:
            return float(fallback)
        index = max(0, min(self._attack_stage - 1, len(values) - 1))
        return float(values[index])

    def _next_attack_stage(self) -> int:
        if (
            self._attack_chain_timer <= 0.0
            or self._attack_stage >= settings.PLAYER_ATTACK_COMBO_COUNT
        ):
            return 1
        return self._attack_stage + 1

    def _start_attack(self, stage: int) -> None:
        max_stage = min(
            settings.PLAYER_ATTACK_COMBO_COUNT,
            len(settings.PLAYER_ATTACK_DURATIONS),
            len(settings.PLAYER_ATTACK_RANGES),
        )
        self._attack_stage = max(1, min(stage, max_stage))
        self._attack_time_left = self.attack_duration
        self._attack_cooldown_left = settings.PLAYER_ATTACK_COOLDOWN
        self._attack_chain_timer = settings.PLAYER_ATTACK_COMBO_RESET_TIME
        self._attack_queued = False
        self._attack_hit_targets.clear()
        self._attack_sound_played = False
        self._attack_animator.play(self._attack, restart=True)
        self.texture = self._attack.textures[0]
        sprites.apply_facing(self, self.facing)

    def cut_jump(self) -> None:
        """Arrete de maintenir : la gravite de coupe ecourte la montee."""
        self._jump_held = False

    def _can_start_jump(self) -> bool:
        if self._physics is None:
            return False
        return self._time_off_ground <= settings.PLAYER_COYOTE_TIME

    def _start_jump(self) -> None:
        if self._physics is None:
            return
        speed = settings.PLAYER_JUMP_SPEED
        max_speed = max(settings.PLAYER_SPEED, 0.001)
        run = min(1.0, abs(self.change_x) / max_speed)
        speed += settings.PLAYER_JUMP_RUN_BONUS * run
        self._physics.jump(speed)
        self._jump_buffer = 0.0
        self._time_off_ground = settings.PLAYER_COYOTE_TIME + 1.0
        self._was_on_ground = False
        if self.is_dashing and self._dash_from_ground:
            self._dash_jump = True
        # Le dash-saut a deja joue dash.wav : evite de superposer le meme sample.
        if not self.is_dashing:
            self._jump_sound_pending = True

    def draw_fx(self) -> None:
        """Trainee de points du dash, halo, et anneau 'dash pret'."""
        self._dash_trail.draw()
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

    def draw_particles(self) -> None:
        """Poussiere de pied, dessinee apres le corps pour rester visible."""
        self._dust.draw()

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        was_attacking = self._attack_time_left > 0.0
        self._attack_time_left = max(0.0, self._attack_time_left - delta_time)
        self._attack_cooldown_left = max(0.0, self._attack_cooldown_left - delta_time)
        self._attack_chain_timer = max(0.0, self._attack_chain_timer - delta_time)
        if was_attacking and self._attack_time_left <= 0.0 and self._attack_queued:
            self._start_attack(self._attack_stage + 1)
        if not self.alive:
            self._death_elapsed += max(0.0, delta_time)
            if self.death_settle_ratio >= 1.0:
                self.texture = self._death.textures[-1]
            else:
                self.texture = self._death.textures[0]
            sprites.apply_facing(self, self.facing)
            return
        if self._physics is None:
            return
        if self.is_attacking:
            self.texture = self._attack_animator.update(delta_time)
            if self.attack_impact_active and not self._attack_sound_played:
                self._attack_sound_played = True
                self._attack_sound_events.append(self._attack_stage)
        else:
            if abs(self.change_x) > 0.05:
                self._animator.play(self._walk)
            elif self._dash_cooldown > 0.0:
                self._animator.play(self._idle_breathe)
            else:
                self._animator.play(self._idle_still)
            self.texture = self._animator.update(delta_time)
        sprites.apply_facing(self, self.facing)
        carried = self.is_dashing or self._dash_jump
        self._tick_dash(delta_time)
        if self.is_dashing:
            self.change_x = self._dash_dir * settings.PLAYER_DASH_SPEED
        else:
            self._apply_horizontal(delta_time)
        if self._jump_buffer > 0.0 and self._can_start_jump():
            self._start_jump()
        self._apply_jump_gravity()
        self._cap_fall_speed()
        fall_speed = max(0.0, -self.change_y)
        old_x = self.center_x
        intended_x = self.change_x
        self._physics.update()
        if carried and self._dash_blocked_by_wall(old_x, intended_x):
            self._stop_dash_against_wall()
        self._cap_fall_speed()
        grounded = self._physics.can_jump()
        if grounded and not self._was_on_ground:
            if not self._standing_on_ice():
                self._landing_timer = settings.PLAYER_LANDING_SLOW_TIME
            self._dust.emit_landing(
                self.center_x,
                self.bottom,
                fall_speed,
                body_half=self.width / 2,
            )
            self._footstep_events.append("land")
            self._footstep_timer = settings.PLAYER_FOOTSTEP_INTERVAL
        self._was_on_ground = grounded
        if grounded:
            self._time_off_ground = 0.0
            self._dash_jump = False
            self._landing_timer = max(0.0, self._landing_timer - delta_time)
            self._tick_run_dust(delta_time)
            self._tick_footsteps(delta_time)
        else:
            self._time_off_ground += delta_time
            self._footstep_timer = 0.0
            self._dust.stop_run()
        self._tick_jump_buffer(delta_time)
        self._dash_trail.follow(
            self.center_x,
            self.center_y,
            self.change_x,
            self.change_y,
            delta_time,
            active=self.is_dashing or self.is_high_speed,
        )
        self._dust.update(delta_time)

    def _tick_jump_buffer(self, delta_time: float) -> None:
        if self._jump_buffer > 0.0:
            self._jump_buffer = max(0.0, self._jump_buffer - delta_time)

    def _apply_jump_gravity(self) -> None:
        """Arc Mario : montee tenue, coupe analogique, descente un peu plus lourde."""
        if self.is_dashing and not self._dash_jump:
            return
        if self.change_y > 0:
            target = (
                settings.PLAYER_JUMP_RISE_GRAVITY
                if self._jump_held
                else settings.PLAYER_JUMP_CUT_GRAVITY
            )
        else:
            target = settings.PLAYER_JUMP_FALL_GRAVITY
        extra = target - settings.PLAYER_GRAVITY
        if extra > 0.0:
            self.change_y -= extra

    def _cap_fall_speed(self) -> None:
        """Plafonne la vitesse de chute (change_y negatif)."""
        max_fall = settings.PLAYER_MAX_FALL_SPEED
        if self.change_y < -max_fall:
            self.change_y = -max_fall

    def _tick_run_dust(self, delta_time: float) -> None:
        full_speed = abs(self.change_x) >= settings.PLAYER_SPEED * settings.PARTICLE_RUN_SPEED_RATIO
        if not full_speed or self._standing_on_ice():
            self._dust.stop_run()
            return
        behind_x = self.center_x - self.facing * (self.width * 0.55)
        self._dust.tick_run(behind_x, self.bottom, self.facing, delta_time)

    def _tick_footsteps(self, delta_time: float) -> None:
        walking = (
            not self.is_dashing
            and not self.is_attacking
            and abs(self.change_x) >= settings.PLAYER_FOOTSTEP_SPEED
        )
        if not walking:
            self._footstep_timer = 0.0
            return
        if self._footstep_timer <= 0.0:
            self._footstep_events.append("step")
            self._footstep_timer = settings.PLAYER_FOOTSTEP_INTERVAL
            return
        self._footstep_timer = max(0.0, self._footstep_timer - delta_time)

    def _dash_blocked_by_wall(self, old_x: float, intended_x: float) -> bool:
        """True si le moteur a absorbe le deplacement horizontal contre un mur."""
        if intended_x == 0.0:
            return False
        moved = self.center_x - old_x
        if intended_x > 0.0:
            return moved < 1.0
        return moved > -1.0

    def _stop_dash_against_wall(self) -> None:
        """Coupe le dash et l'elan horizontal : plus de glissade le long du mur."""
        self._dash_timer = 0.0
        self._dash_jump = False
        self.change_x = 0.0

    def _tick_dash(self, delta_time: float) -> None:
        if self._dash_timer > 0.0:
            self._dash_timer = max(0.0, self._dash_timer - delta_time)
            if self._dash_timer == 0.0 and not self._dash_jump:
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
        on_ice = grounded and self._standing_on_ice()
        landing = grounded and self._landing_timer > 0.0 and not on_ice
        max_speed = settings.PLAYER_SPEED * (
            settings.PLAYER_LANDING_SPEED_SCALE if landing else 1.0
        )
        accel = max_speed / max(settings.PLAYER_ACCEL_TIME, 0.001)
        if on_ice:
            accel *= settings.PLAYER_ICE_ACCEL_SCALE
        direction = self._move_dir
        if grounded:
            if direction == 0:
                slide = (
                    settings.PLAYER_ICE_SLIDE_TIME if on_ice else settings.PLAYER_SLIDE_TIME
                )
                self.change_x += (0.0 - self.change_x) * _exp_alpha(delta_time, slide)
                stop = (
                    settings.PLAYER_ICE_STOP_SPEED if on_ice else 0.18
                )
                if abs(self.change_x) < stop:
                    self.change_x = 0.0
                return
            if self.change_x * direction < 0.0:
                accel *= 1.55
            self.change_x = _approach(self.change_x, direction * max_speed, accel * delta_time)
            return
        if direction == 0:
            if not self._dash_jump:
                self.change_x += (0.0 - self.change_x) * _exp_alpha(
                    delta_time, settings.PLAYER_AIR_BRAKE_TIME
                )
            return
        air_cap = (
            settings.PLAYER_DASH_SPEED if self._dash_jump else settings.PLAYER_SPEED
        )
        air_accel = accel * settings.PLAYER_AIR_CONTROL
        if self.change_x * direction < 0.0:
            air_accel *= settings.PLAYER_AIR_TURN_BOOST
        self.change_x = _approach(
            self.change_x, direction * air_cap, air_accel * delta_time
        )

    def _standing_on_ice(self) -> bool:
        """True si un pied repose sur un bloc `slippery`."""
        if not self._solids:
            return False
        probes = (
            (self.center_x, self.bottom - 2),
            (self.center_x - self.width * 0.28, self.bottom - 2),
            (self.center_x + self.width * 0.28, self.bottom - 2),
        )
        for group in self._solids:
            for probe_x, probe_y in probes:
                for sprite in arcade.get_sprites_at_point((probe_x, probe_y), group):
                    if getattr(sprite, "slippery", False):
                        return True
        return False
