"""Le cadavre laisse par le joueur a chaque mort.

Le cadavre (derniere frame de `player_death`) est solide : plateforme,
bouclier anti-piques, appat. Il finit par se dissiper.

Si un ennemi le devore, il laisse un squelette (`player_bones`) : decor
eternel, sans collision.
"""

from __future__ import annotations

from collections.abc import Sequence

import arcade

import settings
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
    """Depouille physique, ou squelette residuel apres un festin."""

    def __init__(self, center_x: float, center_y: float, facing: int = 1) -> None:
        super().__init__(_cadaver_texture(), center_x=center_x, center_y=center_y)
        sprites.apply_rect_hit_box(
            self,
            settings.PLAYER_WIDTH + 8,
            settings.PLAYER_HEIGHT // 2,
        )
        self.facing = 1 if facing >= 0 else -1
        sprites.apply_facing(self, self.facing)
        self.time_left = settings.CORPSE_LIFETIME
        self.eaten_progress = 0.0
        self.eaters = 0
        self._is_remnant = False
        self._appear = 0.0
        self.alpha = 0
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

    # ------------------------------------------------------------------ #
    # Etat
    # ------------------------------------------------------------------ #

    @property
    def is_remnant(self) -> bool:
        """Squelette laisse apres un festin : plus de collision."""
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
        self._is_remnant = True
        self._physics = None
        self.eaters = 0
        self.time_left = 0.0
        self._appear = 1.0
        self.alpha = 255
        self.texture = _bones_texture()
        sprites.apply_facing(self, self.facing)
        sprites.apply_rect_hit_box(self, 1.0, 1.0)

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        if self._is_remnant:
            return
        if self.eaten_progress >= settings.CORPSE_EAT_TIME:
            self.become_remnant()
            return
        self.time_left = max(0.0, self.time_left - delta_time)
        self.eaters = 0
        if self._physics is not None:
            self._physics.update()
        self.alpha = int(self._fade_alpha() * self._appear)
        if self.is_expired:
            self.remove_from_sprite_lists()

    def _fade_alpha(self) -> int:
        if self.time_left >= settings.CORPSE_FADE_TIME:
            return 255
        return int(255 * self.time_left / settings.CORPSE_FADE_TIME)
