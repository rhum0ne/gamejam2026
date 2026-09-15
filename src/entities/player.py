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
from src.ui import sprites


def _idle_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(settings.SPRITE_PLAYER_IDLE, settings.SPRITE_FRAME_SIZE)
    return sprites.StripAnimation(frames, settings.ANIM_IDLE_FRAME_TIME, loop=True)


def _walk_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(settings.SPRITE_PLAYER_WALK, settings.SPRITE_FRAME_SIZE)
    return sprites.StripAnimation(frames, settings.ANIM_WALK_FRAME_TIME, loop=True)


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
            gravity_constant=settings.GRAVITY,
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
        self._place_on_tile(*position)
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
        if self._physics is not None and self.alive:
            self._physics.update()
            if self._physics.can_jump():
                self._time_off_ground = 0.0
            else:
                self._time_off_ground += delta_time
        if not self.alive:
            return
        if abs(self.change_x) > 0.05:
            self._animator.play(self._walk)
        else:
            self._animator.play(self._idle)
        self.texture = self._animator.update(delta_time)
        sprites.apply_facing(self, self.facing)
