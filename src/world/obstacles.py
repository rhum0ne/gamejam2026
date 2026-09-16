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
from src.entities.glow import draw_glow, draw_threat_glow
from src.entities.particles import SoulBurst
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
        hit_width = size * settings.SPIKE_HITBOX_WIDTH_RATIO
        sprites.apply_rect_hit_box(self, hit_width, hit_height, offset_y=offset_y)

    def draw_ghost_glow(self, *, bind_blend: bool = True) -> None:
        """Halo rouge identique aux ennemis, visible a travers le voile."""
        draw_threat_glow(self.center_x, self.center_y, bind_blend=bind_blend)

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
        self._phase = (center_x * 0.17 + center_y * 0.09) % math.tau
        self.stem = arcade.SpriteSolidColor(
            settings.TORCH_STEM_WIDTH,
            settings.TORCH_STEM_HEIGHT,
            center_x=center_x,
            center_y=self.bottom - settings.TORCH_STEM_HEIGHT / 2,
            color=settings.COLOR_TORCH_STEM,
        )

    def draw_fx(self, *, layer: str = "all") -> None:
        """Halo chaud : bloom large sur le decor, noyau chaud sur la flamme."""
        flicker = self._flicker()
        flame_x = self.center_x
        flame_y = self.center_y
        if layer in ("all", "bloom"):
            draw_glow(
                flame_x,
                flame_y,
                settings.TORCH_GLOW_OUTER * flicker,
                settings.TORCH_GLOW_OUTER * flicker * 1.2,
                settings.COLOR_TORCH_GLOW,
                int(settings.TORCH_GLOW_ALPHA * flicker),
            )
            draw_glow(
                flame_x,
                flame_y,
                settings.TORCH_GLOW_MID * flicker,
                settings.TORCH_GLOW_MID * flicker,
                settings.COLOR_TORCH_GLOW,
                int(settings.TORCH_GLOW_MID_ALPHA * flicker),
            )
        if layer in ("all", "core"):
            draw_glow(
                flame_x,
                flame_y,
                settings.TORCH_GLOW_INNER * flicker,
                settings.TORCH_GLOW_INNER * flicker,
                settings.COLOR_TORCH_GLOW_CORE,
                int(settings.TORCH_GLOW_INNER_ALPHA * flicker),
            )

    def _flicker(self) -> float:
        now = time.perf_counter()
        slow = math.sin(now * settings.TORCH_FLICKER_SPEED + self._phase)
        fast = math.sin(now * settings.TORCH_FLICKER_SPEED_FAST + self._phase * 1.7)
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


class Checkpoint(arcade.Sprite):
    """Point de reapparition du corps physique apres la fin du mode fantome."""

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        display = settings.CHECKPOINT_SIZE
        self._idle = sprites.load_texture(settings.SPRITE_CHECKPOINT)
        self._lit = sprites.load_texture(settings.SPRITE_CHECKPOINT_ACTIVE)
        scale = sprites.scale_for_size(self._idle, display)
        lift = (display - size) / 2
        self._spawn = (center_x, center_y)
        super().__init__(self._idle, scale=scale, center_x=center_x, center_y=center_y + lift)
        sprites.apply_rect_hit_box(self, size, size, offset_y=-lift)
        self.active = False
        self._ignite = 0.0
        self._burst = SoulBurst()

    @property
    def spawn_point(self) -> tuple[float, float]:
        """Centre de la tuile, pas du sprite (la statue est plus haute que la case)."""
        return self._spawn

    def activate(self, *, ignite: bool = True) -> None:
        """Passe a la texture allumee. No-op si deja le checkpoint courant."""
        if self.active:
            return
        self.active = True
        self.texture = self._lit
        if ignite:
            self._ignite = settings.CHECKPOINT_IGNITE_TIME
            self.play_respawn()
            return
        self._ignite = 0.0

    def deactivate(self) -> None:
        """Revient a la texture eteinte."""
        if not self.active:
            return
        self.active = False
        self._ignite = 0.0
        self.texture = self._idle

    def play_respawn(self) -> None:
        """Eclat de motes bleues : le corps revient ici."""
        self._burst.emit(self.center_x, self.center_y + self.height * settings.CHECKPOINT_GLOW_LIFT)

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        self._burst.update(delta_time)
        if self._ignite > 0.0:
            self._ignite = max(0.0, self._ignite - delta_time)

    def draw_glow(self, *, layer: str = "all") -> None:
        """Halo du phenix : flash d'allumage, puis respiration tant qu'il est actif."""
        if layer not in ("all", "bloom", "core"):
            raise ValueError(f"layer inconnu : {layer!r}")
        idle, flash = self._glow_mix()
        if idle <= 0.001 and flash <= 0.001:
            return
        glow_x, glow_y = self._glow_origin()
        size_mul = idle + flash * (settings.CHECKPOINT_IGNITE_PEAK - 1.0)
        alpha_mul = idle + flash * (settings.CHECKPOINT_IGNITE_ALPHA - 1.0)
        if layer in ("all", "bloom"):
            self._stamp_bloom(glow_x, glow_y, size_mul, alpha_mul, flash)
        if layer in ("all", "core"):
            draw_glow(
                glow_x,
                glow_y,
                settings.CHECKPOINT_GLOW_INNER * size_mul,
                settings.CHECKPOINT_GLOW_INNER * size_mul,
                settings.COLOR_CHECKPOINT_GLOW_CORE,
                _glow_alpha(settings.CHECKPOINT_GLOW_INNER_ALPHA * alpha_mul),
            )

    def draw_fx(self) -> None:
        self._burst.draw()

    def _glow_origin(self) -> tuple[float, float]:
        return self.center_x, self.center_y + self.height * settings.CHECKPOINT_GLOW_LIFT

    def _glow_mix(self) -> tuple[float, float]:
        """Retourne (intensite de repos, intensite du flash), chacune dans [0, 1+]."""
        if not self.active:
            return 0.0, 0.0
        pulse = 1.0 + settings.CHECKPOINT_GLOW_PULSE * math.sin(
            time.perf_counter() * settings.CHECKPOINT_GLOW_PULSE_SPEED
            + self.center_x * 0.07
        )
        if self._ignite <= 0.0:
            return pulse, 0.0
        duration = max(settings.CHECKPOINT_IGNITE_TIME, 0.001)
        progress = 1.0 - self._ignite / duration
        rise = max(0.04, min(0.6, settings.CHECKPOINT_IGNITE_RISE))
        if progress < rise:
            flash = (progress / rise) ** 0.55
        else:
            flash = (1.0 - (progress - rise) / (1.0 - rise)) ** 1.55
        idle_in = min(1.0, progress / 0.38)
        return pulse * idle_in, flash

    def _stamp_bloom(
        self,
        glow_x: float,
        glow_y: float,
        size_mul: float,
        alpha_mul: float,
        flash: float,
    ) -> None:
        width_scale = settings.CHECKPOINT_GLOW_WIDTH_SCALE
        wash = settings.CHECKPOINT_GLOW_WASH * size_mul
        outer = settings.CHECKPOINT_GLOW_OUTER * size_mul
        mid = settings.CHECKPOINT_GLOW_MID * size_mul
        draw_glow(
            glow_x,
            glow_y,
            wash * width_scale,
            wash,
            settings.COLOR_CHECKPOINT_GLOW,
            _glow_alpha(settings.CHECKPOINT_GLOW_WASH_ALPHA * alpha_mul),
        )
        draw_glow(
            glow_x,
            glow_y,
            outer * width_scale,
            outer,
            settings.COLOR_CHECKPOINT_GLOW,
            _glow_alpha(settings.CHECKPOINT_GLOW_ALPHA * alpha_mul),
        )
        draw_glow(
            glow_x,
            glow_y,
            mid * width_scale,
            mid,
            settings.COLOR_CHECKPOINT_GLOW,
            _glow_alpha(settings.CHECKPOINT_GLOW_MID_ALPHA * alpha_mul),
        )
        if flash <= 0.02:
            return
        duration = max(settings.CHECKPOINT_IGNITE_TIME, 0.001)
        wave = 1.0 - self._ignite / duration
        flash_size = settings.CHECKPOINT_IGNITE_FLASH_SIZE * (0.28 + 0.72 * wave)
        draw_glow(
            glow_x,
            glow_y,
            flash_size * width_scale,
            flash_size,
            settings.COLOR_CHECKPOINT_GLOW,
            _glow_alpha(settings.CHECKPOINT_IGNITE_FLASH_ALPHA * (1.0 - wave) ** 1.35),
        )


def _glow_alpha(value: float) -> int:
    return max(1, min(255, int(value)))


def is_solid_for_ghost(wall: arcade.Sprite) -> bool:
    """Indique si `wall` bloque le fantome."""
    return not getattr(wall, "ghost_passable", False)
