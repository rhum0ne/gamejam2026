"""Obstacles statiques du decor.

Regle de collision fondamentale du jeu :
    - le corps physique est bloque par tous les murs ;
    - le fantome est bloque par les murs normaux mais traverse les murs
      spectraux (`SpectralWall`, symbole `=` dans les cartes).

Les murs et les piques prennent le sprite nomme dans la legende de la carte
(`"#" : "rock"`, `"G" : "grass"`, `"^" : "spike"`). La hitbox reste un
rectangle plein : changer un PNG ne doit pas modifier la physique.
"""

from __future__ import annotations

from collections.abc import Sequence
import math
import time
from dataclasses import dataclass

import arcade

import settings
from src.entities.glow import draw_glow
from src.ui import sprites


@dataclass(frozen=True, slots=True)
class TileSpec:
    """Description d'une tuile choisie dans la legende d'une carte."""

    sprite: str
    role: str = "wall"
    overlay: bool = False
    flip: bool = False
    hanging: bool = False


def _wall(sprite: str, *, overlay: bool = False, flip: bool = False) -> TileSpec:
    return TileSpec(sprite=sprite, role="wall", overlay=overlay, flip=flip)


def _spike(sprite: str, *, hanging: bool = False) -> TileSpec:
    return TileSpec(sprite=sprite, role="spike", hanging=hanging)


# Noms acceptes dans `legend` d'une carte, en plus des types de gameplay
# (porte, spawn, cle, ...). Les overlays (herbe, coins) sont composes sur
# de la terre pour rester des blocs opaques.
TILE_SPECS: dict[str, TileSpec] = {
    "wall": _wall(settings.SPRITE_DIRT),
    "dirt": _wall(settings.SPRITE_DIRT),
    "dirt_1": _wall(settings.SPRITE_DIRT),
    "rock": _wall(settings.SPRITE_ROCK_1),
    "rock_1": _wall(settings.SPRITE_ROCK_1),
    "rock_2": _wall(settings.SPRITE_ROCK_2),
    "bedrock": _wall(settings.SPRITE_BEDROCK),
    "grass": _wall(settings.SPRITE_GRASS, overlay=True),
    "grass_1": _wall(settings.SPRITE_GRASS_VARIANT, overlay=True),
    "grass_corner": _wall(settings.SPRITE_GRASS_CORNER, overlay=True),
    "grass_corner_right": _wall(settings.SPRITE_GRASS_CORNER, overlay=True, flip=True),
    "dirt_top": _wall(settings.SPRITE_DIRT_TOP, overlay=True),
    "dirt_corner": _wall(settings.SPRITE_DIRT_CORNER, overlay=True),
    "dirt_corner_right": _wall(settings.SPRITE_DIRT_CORNER_RIGHT, overlay=True),
    "dirt_floating_block": _wall(settings.SPRITE_DIRT_FLOATING, overlay=True),
    "spike": _spike(settings.SPRITE_SPIKE),
    "spike_up": _spike(settings.SPRITE_SPIKE_HANGING, hanging=True),
}


def tile_spec(name: str) -> TileSpec:
    """Retourne la spec d'une tuile de terrain, ou leve ValueError."""
    if not name:
        raise ValueError("name ne doit pas etre vide")
    spec = TILE_SPECS.get(name)
    if spec is None:
        raise ValueError(f"tuile inconnue : '{name}'")
    return spec


def terrain_texture(spec: TileSpec, size: int) -> arcade.Texture:
    """Texture d'affichage d'une tuile de mur, deja a la taille de la carte."""
    if spec.role != "wall":
        raise ValueError(f"terrain_texture attend un mur, pas '{spec.role}'")
    if spec.overlay:
        return sprites.tile_texture(
            settings.SPRITE_DIRT,
            spec.sprite,
            flip_overlay=spec.flip,
            size=size,
        )
    return sprites.load_texture(spec.sprite, size=size)


class Wall(arcade.Sprite):
    """Bloc de terrain plein, infranchissable pour tout le monde."""

    ghost_passable = False

    def __init__(
        self,
        center_x: float,
        center_y: float,
        size: int = settings.TILE_SIZE,
        tile: str = settings.SPRITE_DIRT,
    ) -> None:
        spec = tile_spec(tile)
        if spec.role != "wall":
            raise ValueError(f"'{tile}' n'est pas une tuile de mur")
        texture = terrain_texture(spec, size)
        super().__init__(
            texture,
            scale=sprites.scale_for_size(texture, size),
            center_x=center_x,
            center_y=center_y,
        )
        sprites.apply_rect_hit_box(self, size, size)


class SpectralWall(Wall):
    """Mur que seul le fantome peut traverser.

    Indetectable pour le corps physique : il est peint comme de la roche
    normale et ne prend sa teinte spectrale que dans le champ de vision du
    fantome (fiche concept : "devoile les elements invisibles en mode normal").
    """

    ghost_passable = True

    def __init__(
        self,
        center_x: float,
        center_y: float,
        size: int = settings.TILE_SIZE,
        tile: str = "rock",
    ) -> None:
        super().__init__(center_x, center_y, size=size, tile=tile)
        self.revealed = False

    def set_revealed(self, revealed: bool) -> None:
        """Affiche ou masque la nature spectrale du mur."""
        if revealed == self.revealed:
            return
        self.revealed = revealed
        self.color = settings.COLOR_SPECTRAL_WALL if revealed else arcade.color.WHITE


class Spike(arcade.Sprite):
    """Piques : mortelles pour le corps physique, inoffensives pour le fantome.

    La hitbox ne couvre que la moitie de la tuile (bas si posees au sol, haut
    si accrochees au plafond) pour que le joueur puisse raser les piques sans
    mourir injustement.
    """

    def __init__(
        self,
        center_x: float,
        center_y: float,
        size: int = settings.TILE_SIZE,
        tile: str = "spike",
    ) -> None:
        spec = tile_spec(tile)
        if spec.role != "spike":
            raise ValueError(f"'{tile}' n'est pas une tuile de piques")
        texture = sprites.load_texture(spec.sprite, size=size)
        super().__init__(
            texture,
            scale=sprites.scale_for_size(texture, size),
            center_x=center_x,
            center_y=center_y,
        )
        self.lethal_for_body = True
        self.lethal_for_ghost = False
        self.hanging = spec.hanging
        self.falling = False
        self._tile_size = size
        hit_height = size // 2
        offset_y = (size - hit_height) / 2
        if not spec.hanging:
            offset_y = -offset_y
        sprites.apply_rect_hit_box(self, size, hit_height, offset_y=offset_y)

    def draw_ghost_glow(self, *, bind_blend: bool = True) -> None:
        """Halo rouge, visible a travers le voile du fantome."""
        pulse = 1.0 + settings.SPIKE_GHOST_GLOW_PULSE * math.sin(
            time.perf_counter() * settings.SPIKE_GHOST_GLOW_PULSE_SPEED
            + self.center_x * 0.11
            + self.center_y * 0.07
        )
        size = self._tile_size
        draw_glow(
            self.center_x,
            self.center_y,
            size * settings.SPIKE_GHOST_GLOW_SCALE,
            size * settings.SPIKE_GHOST_GLOW_SCALE,
            settings.COLOR_SPIKE_GLOW,
            int(settings.SPIKE_GHOST_GLOW_ALPHA * pulse),
            bind_blend=bind_blend,
        )
        draw_glow(
            self.center_x,
            self.center_y,
            size * settings.SPIKE_GHOST_GLOW_INNER_SCALE,
            size * settings.SPIKE_GHOST_GLOW_INNER_SCALE,
            settings.COLOR_SPIKE_GLOW_CORE,
            int(settings.SPIKE_GHOST_GLOW_INNER_ALPHA * pulse),
            bind_blend=bind_blend,
        )

    def start_fall(self) -> None:
        """Detache la pique du plafond : elle devient un projectile mortel."""
        if self.falling:
            return
        self.hanging = False
        self.falling = True
        self.change_y = 0.0
        sprites.apply_rect_hit_box(self, self._tile_size, self._tile_size)

    def fall(self, walls: Sequence[arcade.SpriteList]) -> bool:
        """Fait tomber la pique. Retourne True si elle a touche le sol (a casser)."""
        if not self.falling:
            return False
        self.change_y -= settings.SPIKE_FALL_GRAVITY
        if self.change_y < -settings.SPIKE_FALL_MAX_SPEED:
            self.change_y = -settings.SPIKE_FALL_MAX_SPEED
        previous_y = self.center_y
        self.center_y += self.change_y
        for wall_list in walls:
            if arcade.check_for_collision_with_list(self, wall_list):
                self.center_y = previous_y
                return True
        if self.top < -settings.TILE_SIZE:
            return True
        return False


class Torch(arcade.SpriteSolidColor):
    """Torche decorative : placeholder solide + halo additif qui vacille.

    Pas de collision : c'est du decor. Le sprite sera remplace plus tard.
    """

    def __init__(self, center_x: float, center_y: float) -> None:
        super().__init__(
            settings.TORCH_WIDTH,
            settings.TORCH_HEIGHT,
            center_x=center_x,
            center_y=center_y + settings.TORCH_STEM_HEIGHT / 2,
            color=settings.COLOR_TORCH_FLAME,
        )
        self._time = 0.0
        self._phase = (center_x * 0.17 + center_y * 0.09) % math.tau

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        self._time += max(0.0, delta_time)

    def draw_fx(self) -> None:
        """Halo chaud, puis le baton du placeholder (la flamme est le sprite)."""
        flicker = self._flicker()
        flame_x = self.center_x
        flame_y = self.center_y
        draw_glow(
            flame_x,
            flame_y,
            settings.TORCH_GLOW_OUTER * flicker,
            settings.TORCH_GLOW_OUTER * flicker * 1.15,
            settings.COLOR_TORCH_GLOW,
            int(settings.TORCH_GLOW_ALPHA * flicker),
        )
        draw_glow(
            flame_x,
            flame_y,
            settings.TORCH_GLOW_INNER * flicker,
            settings.TORCH_GLOW_INNER * flicker,
            settings.COLOR_TORCH_GLOW_CORE,
            int(settings.TORCH_GLOW_INNER_ALPHA * flicker),
        )
        stem_top = self.bottom
        stem_bottom = stem_top - settings.TORCH_STEM_HEIGHT
        half = settings.TORCH_STEM_WIDTH / 2
        arcade.draw_lrbt_rectangle_filled(
            self.center_x - half,
            self.center_x + half,
            stem_bottom,
            stem_top,
            settings.COLOR_TORCH_STEM,
        )

    def _flicker(self) -> float:
        slow = math.sin(self._time * settings.TORCH_FLICKER_SPEED + self._phase)
        fast = math.sin(self._time * settings.TORCH_FLICKER_SPEED_FAST + self._phase * 1.7)
        return 1.0 + settings.TORCH_FLICKER * (0.65 * slow + 0.35 * fast)


class Door(arcade.SpriteSolidColor):
    """Porte de fin de niveau, verrouillee jusqu'a l'obtention de la cle."""

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        super().__init__(
            size,
            size * 2,
            center_x=center_x,
            center_y=center_y + size / 2,
            color=settings.COLOR_DOOR_LOCKED,
        )
        self.locked = True

    def unlock(self) -> None:
        """Deverrouille la porte (feedback visuel provisoire : changement de couleur)."""
        if not self.locked:
            return
        self.locked = False
        self.color = settings.COLOR_DOOR_OPEN


class Checkpoint(arcade.SpriteSolidColor):
    """Point de reapparition du corps physique apres la fin du mode fantome."""

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        super().__init__(
            size // 2,
            size,
            center_x=center_x,
            center_y=center_y,
            color=settings.COLOR_CHECKPOINT,
        )
        self.active = False

    def activate(self) -> None:
        self.active = True
        self.color = settings.COLOR_HUD_BAR_FILL


def is_solid_for_ghost(wall: arcade.Sprite) -> bool:
    """Indique si `wall` bloque le fantome."""
    return not getattr(wall, "ghost_passable", False)
