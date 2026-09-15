"""Le corps physique du joueur.

Responsabilites : deplacement lateral, saut (avec coyote time), gravite via
`arcade.PhysicsEnginePlatformer`, inventaire et etat vivant / mort.

Ce module ne connait ni le fantome ni les etats de jeu : la transition
"mort -> mode fantome" est orchestree par `src.systems.game_state`.
"""

from __future__ import annotations

from collections.abc import Sequence

import arcade

import settings
from src.entities.item import ItemKind


class Player(arcade.SpriteSolidColor):
    """Corps physique controle au clavier."""

    def __init__(self, center_x: float, center_y: float) -> None:
        super().__init__(
            settings.PLAYER_WIDTH,
            settings.PLAYER_HEIGHT,
            center_x=center_x,
            center_y=center_y,
            color=settings.COLOR_PLAYER,
        )
        self.alive = True
        self.facing = 1
        self.inventory: set[ItemKind] = set()
        self.respawn_point: tuple[float, float] = (center_x, center_y)
        self._physics: arcade.PhysicsEnginePlatformer | None = None
        self._time_off_ground = 0.0

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(self, platforms: Sequence[arcade.SpriteList]) -> None:
        """Branche le moteur de physique sur les listes de plateformes.

        Les listes sont conservees par reference : ajouter un cadavre a la
        `SpriteList` des cadavres le rend immediatement solide, sans avoir a
        reconstruire le moteur.
        """
        self._physics = arcade.PhysicsEnginePlatformer(
            self,
            walls=list(platforms),
            gravity_constant=settings.GRAVITY,
        )

    # ------------------------------------------------------------------ #
    # Etat
    # ------------------------------------------------------------------ #

    @property
    def on_ground(self) -> bool:
        return self._physics is not None and self._physics.can_jump()

    def has_item(self, kind: ItemKind) -> bool:
        return kind in self.inventory

    def give_item(self, kind: ItemKind) -> None:
        self.inventory.add(kind)

    def die(self) -> None:
        """Marque le corps comme mort et l'immobilise."""
        self.alive = False
        self.change_x = 0.0
        self.change_y = 0.0

    def respawn_at(self, position: tuple[float, float]) -> None:
        """Fait reapparaitre le corps au checkpoint fourni."""
        self.alive = True
        self.center_x, self.center_y = position
        self.change_x = 0.0
        self.change_y = 0.0
        self._time_off_ground = 0.0

    # ------------------------------------------------------------------ #
    # Commandes
    # ------------------------------------------------------------------ #

    def walk(self, direction: int) -> None:
        """Applique une direction horizontale : -1 (gauche), 0, ou 1 (droite)."""
        self.change_x = direction * settings.PLAYER_SPEED
        if direction != 0:
            self.facing = direction

    def jump(self) -> bool:
        """Tente un saut. Retourne True si le saut a ete declenche."""
        if not self.alive or self._physics is None:
            return False
        if self._time_off_ground > settings.PLAYER_COYOTE_TIME:
            return False
        self._physics.jump(settings.PLAYER_JUMP_SPEED)
        self._time_off_ground = settings.PLAYER_COYOTE_TIME + 1.0
        return True

    def cut_jump(self) -> None:
        """Ecourte le saut quand la touche est relachee (saut a hauteur variable)."""
        if self.change_y > 0:
            self.change_y *= 0.4

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        if self._physics is None or not self.alive:
            return
        self._physics.update()
        if self._physics.can_jump():
            self._time_off_ground = 0.0
        else:
            self._time_off_ground += delta_time
