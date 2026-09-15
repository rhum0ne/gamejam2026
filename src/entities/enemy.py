"""Ennemis : IA basique et liberation d'une "bille bleue" a leur mort.

Priorites de comportement, de la plus forte a la plus faible :
    1. FEAST  : un cadavre est a portee d'odorat -> l'ennemi va le devorer
                (c'est le coeur de la mecanique d'appat) ;
    2. CHASE  : le corps physique vivant est a portee -> poursuite ;
    3. PATROL : va-et-vient, demi-tour devant un mur ou au bord d'une plateforme.

TODO(gameplay) : varier les archetypes (volant, spectral visible uniquement en
mode fantome, tireur) en sous-classant `Enemy`.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum, auto

import arcade

import settings
from src.entities.corpse import Corpse
from src.entities.item import Item, make_soul_orb
from src.entities.player import Player


class EnemyState(Enum):
    """Etats de l'IA."""

    PATROL = auto()
    CHASE = auto()
    FEAST = auto()


class Enemy(arcade.SpriteSolidColor):
    """Ennemi terrestre carnivore."""

    def __init__(self, center_x: float, center_y: float) -> None:
        super().__init__(
            settings.ENEMY_WIDTH,
            settings.ENEMY_HEIGHT,
            center_x=center_x,
            center_y=center_y,
            color=settings.COLOR_ENEMY,
        )
        self.state = EnemyState.PATROL
        self.facing = -1
        self.hit_points = 1
        self._physics: arcade.PhysicsEnginePlatformer | None = None
        self._ground: arcade.SpriteList | None = None

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(self, platforms: Sequence[arcade.SpriteList]) -> None:
        """Branche la physique de l'ennemi sur les plateformes du niveau."""
        self._physics = arcade.PhysicsEnginePlatformer(
            self,
            walls=list(platforms),
            gravity_constant=settings.GRAVITY,
        )
        self._ground = platforms[0] if platforms else None

    # ------------------------------------------------------------------ #
    # Mort
    # ------------------------------------------------------------------ #

    def take_damage(self, amount: int = 1) -> Item | None:
        """Applique des degats. Retourne la bille bleue si l'ennemi meurt."""
        if amount <= 0:
            raise ValueError("amount doit etre strictement positif")
        self.hit_points -= amount
        if self.hit_points > 0:
            return None
        orb = make_soul_orb(self.center_x, self.center_y)
        self.remove_from_sprite_lists()
        return orb

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
        target_corpse = self._closest_corpse(corpses)
        if target_corpse is not None:
            self._feast(delta_time, target_corpse)
        elif self._player_in_range(player):
            self._chase(player)
        else:
            self._patrol()
        if self._physics is not None:
            self._physics.update()

    # ------------------------------------------------------------------ #
    # Comportements
    # ------------------------------------------------------------------ #

    def _closest_corpse(self, corpses: arcade.SpriteList | None) -> Corpse | None:
        if not corpses:
            return None
        in_range = [
            corpse
            for corpse in corpses
            if arcade.get_distance_between_sprites(self, corpse) <= settings.ENEMY_CORPSE_SMELL_RANGE
        ]
        if not in_range:
            return None
        return min(in_range, key=lambda corpse: arcade.get_distance_between_sprites(self, corpse))

    def _feast(self, delta_time: float, corpse: Corpse) -> None:
        self.state = EnemyState.FEAST
        if arcade.check_for_collision(self, corpse):
            self.change_x = 0.0
            corpse.eaters += 1
            corpse.feed(delta_time)
            return
        self._walk_towards(corpse.center_x)

    def _chase(self, player: Player) -> None:
        self.state = EnemyState.CHASE
        self._walk_towards(player.center_x)

    def _patrol(self) -> None:
        self.state = EnemyState.PATROL
        if self._blocked_ahead() or not self._floor_ahead():
            self.facing = -self.facing
        self.change_x = self.facing * settings.ENEMY_SPEED

    def _player_in_range(self, player: Player | None) -> bool:
        if player is None or not player.alive:
            return False
        return arcade.get_distance_between_sprites(self, player) <= settings.ENEMY_AGGRO_RANGE

    def _walk_towards(self, target_x: float) -> None:
        direction = 1 if target_x > self.center_x else -1
        self.facing = direction
        self.change_x = direction * settings.ENEMY_SPEED

    def _blocked_ahead(self) -> bool:
        if self._ground is None:
            return False
        probe = (self.center_x + self.facing * (self.width / 2 + 4), self.center_y)
        return bool(arcade.get_sprites_at_point(probe, self._ground))

    def _floor_ahead(self) -> bool:
        if self._ground is None:
            return True
        probe = (self.center_x + self.facing * (self.width / 2 + 4), self.bottom - 4)
        return bool(arcade.get_sprites_at_point(probe, self._ground))
