"""La forme fantome : projection astrale du joueur apres sa mort.

Specificites par rapport au corps physique :
    - aucune gravite, deplacement libre dans les 8 directions ;
    - traverse les murs spectraux (`SpectralWall`) mais pas les murs normaux ;
    - reste attache au cadavre par une "longe" de longueur `stats.max_range` ;
    - possede un timer : a zero, le corps reapparait au checkpoint ;
    - peut transporter des objets jusqu'au cadavre pour les livrer au corps.
"""

from __future__ import annotations

import math

import arcade

import settings
from src.entities.item import Item
from src.systems.upgrades import GhostStats


class Ghost(arcade.SpriteSolidColor):
    """Esprit desincarne, ancre sur le cadavre qui vient d'etre laisse."""

    def __init__(
        self,
        center_x: float,
        center_y: float,
        stats: GhostStats,
        anchor: tuple[float, float] | None = None,
    ) -> None:
        super().__init__(
            settings.GHOST_WIDTH,
            settings.GHOST_HEIGHT,
            center_x=center_x,
            center_y=center_y,
            color=settings.COLOR_GHOST,
        )
        self.stats = stats
        self.anchor = anchor if anchor is not None else (center_x, center_y)
        self.time_left = stats.duration
        self.carried: list[Item] = []
        self._input = (0.0, 0.0)
        self._solid_walls: arcade.SpriteList | None = None

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(self, solid_walls: arcade.SpriteList) -> None:
        """Definit les murs opaques au fantome (murs spectraux exclus)."""
        self._solid_walls = solid_walls

    # ------------------------------------------------------------------ #
    # Etat
    # ------------------------------------------------------------------ #

    @property
    def vision_radius(self) -> float:
        return self.stats.vision_radius

    @property
    def expired(self) -> bool:
        return self.time_left <= 0.0

    @property
    def distance_to_anchor(self) -> float:
        return math.dist((self.center_x, self.center_y), self.anchor)

    @property
    def leash_ratio(self) -> float:
        """Part de la longe consommee, entre 0.0 et 1.0."""
        if self.stats.max_range <= 0:
            return 1.0
        return min(1.0, self.distance_to_anchor / self.stats.max_range)

    def reveals(self, sprite: arcade.Sprite) -> bool:
        """Indique si `sprite` est dans le champ de revelation du fantome."""
        return math.dist((self.center_x, self.center_y), sprite.position) <= self.vision_radius

    # ------------------------------------------------------------------ #
    # Commandes
    # ------------------------------------------------------------------ #

    def steer(self, dx: float, dy: float) -> None:
        """Enregistre la direction demandee par le joueur (composantes -1..1)."""
        self._input = (dx, dy)

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
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        self.time_left = max(0.0, self.time_left - delta_time)
        self._apply_steering(delta_time)
        self._move_axis("x")
        self._move_axis("y")
        self._clamp_to_leash()

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

    def _clamp_to_leash(self) -> None:
        """Empeche le fantome de s'eloigner du cadavre au-dela de sa portee."""
        anchor_x, anchor_y = self.anchor
        offset_x = self.center_x - anchor_x
        offset_y = self.center_y - anchor_y
        distance = math.hypot(offset_x, offset_y)
        if distance <= self.stats.max_range or distance == 0:
            return
        scale = self.stats.max_range / distance
        self.center_x = anchor_x + offset_x * scale
        self.center_y = anchor_y + offset_y * scale
        radial = (self.change_x * offset_x + self.change_y * offset_y) / distance
        if radial > 0:
            self.change_x -= radial * offset_x / distance
            self.change_y -= radial * offset_y / distance
