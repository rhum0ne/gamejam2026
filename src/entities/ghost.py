"""La forme fantome : projection astrale du joueur apres sa mort.

Specificites par rapport au corps physique :
    - aucune gravite, deplacement libre dans les 8 directions ;
    - traverse les murs spectraux (`SpectralWall`) mais pas les murs normaux ;
    - possede un timer : a zero, le corps reapparait au checkpoint ;
    - peut transporter des objets jusqu'au cadavre pour les livrer au corps.
"""

from __future__ import annotations

import math

import arcade

import settings
from src.entities.glow import draw_glow
from src.entities.item import Item
from src.entities.trail import PointTrail
from src.systems.upgrades import GhostStats
from src.ui import sprites


def _walk_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.SPRITE_GHOST_WALK,
        settings.SPRITE_FRAME_SIZE,
        scale=settings.ENTITY_SCALE,
    )
    return sprites.StripAnimation(frames, settings.ANIM_WALK_FRAME_TIME, loop=True)


def _disappear_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.SPRITE_GHOST_DISAPPEAR,
        settings.SPRITE_FRAME_SIZE,
        scale=settings.ENTITY_SCALE,
    )
    return sprites.StripAnimation(frames, settings.ANIM_GHOST_DISAPPEAR_FRAME_TIME, loop=False)


class Ghost(arcade.Sprite):
    """Esprit desincarne, ancre sur le cadavre qui vient d'etre laisse."""

    def __init__(
        self,
        center_x: float,
        center_y: float,
        stats: GhostStats,
        anchor: tuple[float, float] | None = None,
    ) -> None:
        self._walk = _walk_animation()
        self._disappear = _disappear_animation()
        super().__init__(self._walk.textures[0], center_x=center_x, center_y=center_y)
        sprites.apply_rect_hit_box(
            self,
            settings.GHOST_WIDTH * settings.ENTITY_SCALE,
            settings.GHOST_HEIGHT * settings.ENTITY_SCALE,
        )
        self._animator = sprites.Animator(self._walk)
        self.stats = stats
        self.anchor = anchor if anchor is not None else (center_x, center_y)
        self.time_left = stats.duration
        self.carried: list[Item] = []
        self.facing = 1
        self._vanishing = False
        self._input = (0.0, 0.0)
        self._solid_walls: arcade.SpriteList | None = None
        self._glow_time = 0.0
        self._trail = PointTrail(
            settings.COLOR_TRAIL_GHOST,
            settings.COLOR_TRAIL_GHOST_CORE,
        )

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(self, solid_walls: arcade.SpriteList) -> None:
        """Definit les murs opaques au fantome (murs spectraux exclus)."""
        self._solid_walls = solid_walls
        self._separate_from_walls()

    def _separate_from_walls(self) -> None:
        """Remonte le fantome s'il nait a cheval sur un mur (sprite agrandi)."""
        max_lift = int(abs(self.height)) + settings.TILE_SIZE
        for _ in range(max_lift):
            if not arcade.check_for_collision_with_list(self, self._solid_walls):
                return
            self.center_y += 1

    # ------------------------------------------------------------------ #
    # Etat
    # ------------------------------------------------------------------ #

    @property
    def timer_spent(self) -> float:
        """Part du timer ecoulee, de 0.0 (debut) a 1.0 (expire)."""
        duration = max(self.stats.duration, 0.001)
        return 1.0 - max(0.0, min(1.0, self.time_left / duration))

    @property
    def vision_radius(self) -> float:
        """Rayon de vision : part de `stats.vision_radius` et se referme avec le timer.

        La courbe est une puissance : le trou reste large longtemps, puis
        s'effondre d'un coup en fin de timer, sans rester petit trop longtemps.
        """
        eased = self.timer_spent ** settings.GHOST_VISION_SHRINK_POWER
        start = self.stats.vision_radius
        end = settings.GHOST_VISION_RADIUS_MIN
        return start + (end - start) * eased

    @property
    def warp_strength(self) -> float:
        """Intensite du filtre de perspective, qui monte legerement avec le timer."""
        start = settings.GHOST_WARP_STRENGTH
        end = settings.GHOST_WARP_STRENGTH_MAX
        return start + (end - start) * self.timer_spent

    @property
    def expired(self) -> bool:
        return self.time_left <= 0.0

    @property
    def vanishing(self) -> bool:
        return self._vanishing

    @property
    def vanished(self) -> bool:
        return self._vanishing and self._animator.finished

    @property
    def vanish_duration(self) -> float:
        """Duree reelle de l'animation de disparition, deja affectee par ANIM_SPEED."""
        animation = self._disappear
        return animation.frame_time * len(animation.textures) / self._animator.speed

    @property
    def distance_to_anchor(self) -> float:
        return math.dist((self.center_x, self.center_y), self.anchor)

    @property
    def leash_ratio(self) -> float:
        """Ancienne tension de longe : plus de limite de distance, toujours 0."""
        return 0.0

    def reveals(self, sprite: arcade.Sprite) -> bool:
        """Indique si `sprite` est dans le champ de revelation du fantome."""
        return math.dist((self.center_x, self.center_y), sprite.position) <= self.vision_radius

    # ------------------------------------------------------------------ #
    # Commandes
    # ------------------------------------------------------------------ #

    def steer(self, dx: float, dy: float) -> None:
        """Enregistre la direction demandee par le joueur (composantes -1..1)."""
        if self._vanishing:
            self._input = (0.0, 0.0)
            return
        self._input = (dx, dy)

    def start_vanish(self) -> None:
        """Joue l'animation de disparition une fois, sans deplacement."""
        if self._vanishing:
            return
        self._vanishing = True
        self.change_x = 0.0
        self.change_y = 0.0
        self._input = (0.0, 0.0)
        self._animator.play(self._disappear)

    def can_carry_more(self) -> bool:
        return len(self.carried) < self.stats.carry_capacity

    def pick_up(self, item: Item) -> bool:
        """Saisit un objet a distance. Retourne True si la prise a reussi."""
        if not item.profile.ghost_can_carry or not self.can_carry_more():
            return False
        item.attach_to(self)
        self.carried.append(item)
        return True

    def release_all(self) -> list[Item]:
        """Lache tous les objets transportes et retourne la liste correspondante."""
        released = list(self.carried)
        self.carried.clear()
        for item in released:
            item.drop_at(self.center_x, self.center_y)
        return released

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #

    def draw_fx(self) -> None:
        """Trainee de points cyan, puis halo."""
        self._trail.draw()
        pulse = 1.0 + settings.GHOST_GLOW_PULSE * math.sin(
            self._glow_time * settings.GHOST_GLOW_PULSE_SPEED
        )
        draw_glow(
            self.center_x,
            self.center_y,
            settings.GHOST_WIDTH * settings.GHOST_GLOW_SCALE,
            settings.GHOST_HEIGHT * settings.GHOST_GLOW_SCALE,
            settings.COLOR_GHOST_GLOW,
            int(settings.GHOST_GLOW_ALPHA * pulse),
        )

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        self.time_left = max(0.0, self.time_left - delta_time)
        if not self._vanishing and self.time_left <= self.vanish_duration:
            self.start_vanish()
        if self._vanishing:
            self._advance_animation(delta_time)
            return
        self._glow_time += max(0.0, delta_time)
        self._apply_steering(delta_time)
        self._move_axis("x")
        self._move_axis("y")
        speed = math.hypot(self.change_x, self.change_y)
        self._trail.follow(
            self.center_x,
            self.center_y,
            self.change_x,
            self.change_y,
            delta_time,
            active=speed >= settings.TRAIL_MIN_SPEED,
        )
        if abs(self.change_x) > 0.05:
            self.facing = 1 if self.change_x > 0 else -1
        self._advance_animation(delta_time)

    def _advance_animation(self, delta_time: float) -> None:
        self.texture = self._animator.update(delta_time)
        sprites.apply_facing(self, self.facing)

    def _apply_steering(self, delta_time: float) -> None:
        dx, dy = self._input
        length = math.hypot(dx, dy)
        if length > 0:
            dx, dy = dx / length, dy / length
            smooth_time = settings.GHOST_ACCEL_TIME
        else:
            smooth_time = settings.GHOST_COAST_TIME
        alpha = 1.0 - math.exp(-max(delta_time, 0.0) / max(smooth_time, 0.001))
        self.change_x += (dx * settings.GHOST_SPEED - self.change_x) * alpha
        self.change_y += (dy * settings.GHOST_SPEED - self.change_y) * alpha

    def _move_axis(self, axis: str) -> None:
        """Deplace le fantome sur un seul axe et annule le pas en cas de collision."""
        if axis == "x":
            previous, self.center_x = self.center_x, self.center_x + self.change_x
        else:
            previous, self.center_y = self.center_y, self.center_y + self.change_y
        if self._solid_walls is None:
            return
        if arcade.check_for_collision_with_list(self, self._solid_walls):
            if axis == "x":
                self.center_x = previous
                self.change_x = 0.0
            else:
                self.center_y = previous
                self.change_y = 0.0
