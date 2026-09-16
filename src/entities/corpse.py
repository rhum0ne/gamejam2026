"""Le cadavre laisse par le joueur a chaque mort.

Le cadavre (derniere frame de `player_death`) est solide : plateforme,
bouclier anti-piques, appat. En fin de vie, ou si un ennemi le devore, il
devient un squelette (`player_bones`) : decor eternel, sans collision.
Un nuage de particules masque le changement de sprite.
"""

from __future__ import annotations

from collections.abc import Sequence

import arcade

import settings
from src.entities.particles import DecayBurst
from src.ui import sprites


def _cadaver_texture() -> arcade.Texture:
    frames = sprites.load_strip(
        settings.SPRITE_PLAYER_DEATH,
        settings.SPRITE_FRAME_SIZE,
        scale=settings.ENTITY_SCALE,
    )
    return frames[-1]


def _bones_texture() -> arcade.Texture:
    frames = sprites.load_strip(
        settings.SPRITE_PLAYER_BONES,
        settings.SPRITE_FRAME_SIZE,
        scale=settings.ENTITY_SCALE,
    )
    return frames[0]


class Corpse(arcade.Sprite):
    """Depouille physique, ou squelette residuel."""

    def __init__(self, center_x: float, center_y: float, facing: int = 1) -> None:
        super().__init__(_cadaver_texture(), center_x=center_x, center_y=center_y)
        self._apply_body_hit_box()
        self.facing = 1 if facing >= 0 else -1
        sprites.apply_facing(self, self.facing)
        self.time_left = settings.CORPSE_LIFETIME
        self.eaten_progress = 0.0
        self.eaters = 0
        self._is_remnant = False
        self._appear = 0.0
        self._bones_in = 1.0
        self.alpha = 0
        self._decay = DecayBurst()
        self._physics: arcade.PhysicsEnginePlatformer | None = None

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(self, platforms: Sequence[arcade.SpriteList]) -> None:
        """Donne une gravite au cadavre pour qu'il tombe sur le sol le plus proche."""
        if self._is_remnant:
            return
        self._physics = arcade.PhysicsEnginePlatformer(
            self,
            walls=list(platforms),
            gravity_constant=settings.GRAVITY,
        )

    def _apply_body_hit_box(self) -> None:
        """Cale la collision sur le sol sans y enterrer le sprite allonge."""
        hit_height = settings.CORPSE_HITBOX_HEIGHT
        offset_y = (hit_height - abs(self.height)) / 2 - settings.CORPSE_GROUND_LIFT
        sprites.apply_rect_hit_box(
            self,
            settings.CORPSE_HITBOX_WIDTH,
            hit_height,
            offset_y=offset_y,
        )

    # ------------------------------------------------------------------ #
    # Etat
    # ------------------------------------------------------------------ #

    @property
    def is_remnant(self) -> bool:
        """Squelette residuel : plus de collision."""
        return self._is_remnant

    @property
    def is_expired(self) -> bool:
        return not self._is_remnant and self.time_left <= 0.0

    @property
    def is_being_eaten(self) -> bool:
        return not self._is_remnant and self.eaters > 0

    def set_appear(self, ratio: float) -> None:
        """0 = encore invisible (fondu de mort), 1 = cadavre montre."""
        self._appear = max(0.0, min(1.0, ratio))

    def feed(self, delta_time: float) -> None:
        """Fait progresser la consommation du cadavre par un ennemi."""
        if self._is_remnant:
            return
        self.eaten_progress += delta_time

    def become_remnant(self) -> None:
        """Remplace le cadavre par un tas d'os inerte, sans hitbox."""
        if self._is_remnant:
            return
        self._decay.emit(self.center_x, self.center_y)
        self._is_remnant = True
        self._physics = None
        self.eaters = 0
        self.time_left = 0.0
        self._appear = 1.0
        self._bones_in = 0.0
        self.alpha = 0
        self.texture = _bones_texture()
        sprites.apply_facing(self, self.facing)
        sprites.apply_rect_hit_box(self, 1.0, 1.0)

    def draw_fx(self) -> None:
        self._decay.draw()

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        dt = max(0.0, delta_time)
        if self._is_remnant:
            self._decay.update(dt)
            fade = max(settings.CORPSE_FADE_TIME, 0.001)
            self._bones_in = min(1.0, self._bones_in + dt / fade)
            self.alpha = int(255 * self._bones_in)
            return
        if self.eaten_progress >= settings.CORPSE_EAT_TIME:
            self.become_remnant()
            return
        self.time_left = max(0.0, self.time_left - dt)
        self.eaters = 0
        if self._physics is not None:
            self._physics.update()
        if self.is_expired:
            self.become_remnant()
            return
        self.alpha = int(255 * self._appear)
