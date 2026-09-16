"""Le cadavre laisse par le joueur a chaque mort.

Proprietes (fiche concept, systeme 3) :
    - collision solide : sert de plateforme et de bouclier contre les piques ;
    - appat : les ennemis carnivores s'arretent pour le devorer ;
    - duree de vie limitee, avec un fondu avant dissipation.

Le cadavre est ajoute a une `SpriteList` dediee, elle-meme passee au moteur de
physique du joueur : il devient donc solide des son apparition.
"""

from __future__ import annotations

from collections.abc import Sequence

import arcade

import settings
from src.ui import sprites


def _bones_texture() -> arcade.Texture:
    frames = sprites.load_strip(
        settings.SPRITE_PLAYER_BONES,
        settings.SPRITE_FRAME_SIZE,
        scale=settings.ENTITY_SCALE,
    )
    return frames[0]


class Corpse(arcade.Sprite):
    """Depouille physique, solide et perissable (tas d'os)."""

    def __init__(self, center_x: float, center_y: float) -> None:
        super().__init__(_bones_texture(), center_x=center_x, center_y=center_y)
        sprites.apply_rect_hit_box(
            self,
            settings.PLAYER_WIDTH + 8,
            settings.PLAYER_HEIGHT // 2,
        )
        self.time_left = settings.CORPSE_LIFETIME
        self.eaten_progress = 0.0
        self.eaters = 0
        self._physics: arcade.PhysicsEnginePlatformer | None = None

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(self, platforms: Sequence[arcade.SpriteList]) -> None:
        """Donne une gravite au cadavre pour qu'il tombe sur le sol le plus proche."""
        self._physics = arcade.PhysicsEnginePlatformer(
            self,
            walls=list(platforms),
            gravity_constant=settings.GRAVITY,
        )

    # ------------------------------------------------------------------ #
    # Etat
    # ------------------------------------------------------------------ #

    @property
    def is_expired(self) -> bool:
        return self.time_left <= 0.0 or self.eaten_progress >= settings.CORPSE_EAT_TIME

    @property
    def is_being_eaten(self) -> bool:
        return self.eaters > 0

    def feed(self, delta_time: float) -> None:
        """Fait progresser la consommation du cadavre par un ennemi."""
        self.eaten_progress += delta_time

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        self.time_left = max(0.0, self.time_left - delta_time)
        self.eaters = 0
        if self._physics is not None:
            self._physics.update()
        self.alpha = self._fade_alpha()
        if self.is_expired:
            self.remove_from_sprite_lists()

    def _fade_alpha(self) -> int:
        if self.time_left >= settings.CORPSE_FADE_TIME:
            return 255
        return int(255 * self.time_left / settings.CORPSE_FADE_TIME)
