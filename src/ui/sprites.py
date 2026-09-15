"""Chargement, cache et composition des textures.

Module feuille : n'importe que `arcade` et `settings`. Les tuiles, et plus
tard les entites / objets, passent par ici pour recuperer un sprite plutot
que de recharger un PNG a chaque construction.

Les images de tuiles font 16 px ; on les agrandit en nearest-neighbor jusqu'a
`TILE_SIZE`. Les bandeaux d'entites (marche, disparition) sont decoupes par
`load_strip` / `Animator`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import arcade
from arcade.hitbox import HitBox
from PIL import Image

import settings

_IMAGE_CACHE: dict[str, Image.Image] = {}
_TEXTURE_CACHE: dict[str, arcade.Texture] = {}
_STRIP_CACHE: dict[str, tuple[arcade.Texture, ...]] = {}


def sprite_path(name: str) -> Path:
    """Retourne le chemin d'un sprite dans `settings.SPRITES_DIR`.

    `name` accepte `spike` ou `spike.png`.
    """
    if not name:
        raise ValueError("name ne doit pas etre vide")
    filename = name if name.endswith(".png") else f"{name}.png"
    return settings.SPRITES_DIR / filename


def load_texture(name: str, *, size: int | None = None) -> arcade.Texture:
    """Charge une texture et la met en cache.

    Si `size` est fourni, l'image est redimensionnee en carre de ce cote
    (filtre nearest-neighbor).
    """
    if size is not None and size <= 0:
        raise ValueError("size doit etre strictement positif")
    key = f"raw:{name}|{size or 0}"
    cached = _TEXTURE_CACHE.get(key)
    if cached is not None:
        return cached
    image = _open_image(name)
    if size is not None and image.size != (size, size):
        image = image.resize((size, size), Image.Resampling.NEAREST)
    texture = arcade.Texture(image, hash=key)
    _TEXTURE_CACHE[key] = texture
    return texture


def soul_orb_texture(size: int = 32) -> arcade.Texture:
    """Boule translucide (degrade radial), a teinter via `sprite.color`."""
    if size <= 0:
        raise ValueError("size doit etre strictement positif")
    cache_key = f"soul-orb|{size}"
    cached = _TEXTURE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    radius = size / 2
    pixels = bytearray(size * size * 4)
    for y in range(size):
        dy = y + 0.5 - radius
        row = y * size * 4
        for x in range(size):
            dx = x + 0.5 - radius
            t = math.hypot(dx, dy) / radius
            if t >= 1.0:
                continue
            rest = 1.0 - t
            falloff = rest * rest
            core = falloff * falloff
            value = int(255 * min(1.0, falloff * 0.55 + core * 0.7))
            alpha = int(255 * min(1.0, falloff * 0.85))
            if value == 0 and alpha == 0:
                continue
            index = row + x * 4
            pixels[index] = value
            pixels[index + 1] = value
            pixels[index + 2] = value
            pixels[index + 3] = alpha
    image = Image.frombytes("RGBA", (size, size), bytes(pixels))
    texture = arcade.Texture(image, hash=cache_key)
    _TEXTURE_CACHE[cache_key] = texture
    return texture


def tile_texture(
    fill: str,
    overlay: str | None = None,
    *,
    flip_overlay: bool = False,
    size: int = settings.TILE_SIZE,
) -> arcade.Texture:
    """Compose une tuile : fond opaque + overlay eventuel (herbe, coins, etc.)."""
    if size <= 0:
        raise ValueError("size doit etre strictement positif")
    if not fill:
        raise ValueError("fill ne doit pas etre vide")
    key = f"tile:{fill}|{overlay}|{int(flip_overlay)}|{size}"
    cached = _TEXTURE_CACHE.get(key)
    if cached is not None:
        return cached

    canvas = _open_image(fill).resize((size, size), Image.Resampling.NEAREST)
    if overlay is not None:
        overlay_image = _open_image(overlay)
        if flip_overlay:
            overlay_image = overlay_image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        overlay_image = _scale_overlay(overlay_image, size)
        canvas.paste(overlay_image, (0, 0), overlay_image)

    texture = arcade.Texture(canvas, hash=key)
    _TEXTURE_CACHE[key] = texture
    return texture


def load_strip(
    name: str,
    frame_width: int,
    frame_height: int | None = None,
) -> tuple[arcade.Texture, ...]:
    """Decoupe un bandeau horizontal en frames, avec cache.

    `frame_height` defaut a la hauteur de l'image. Les pixels restants a
    droite (largeur non multiple) sont ignores.
    """
    if frame_width <= 0:
        raise ValueError("frame_width doit etre strictement positif")
    if frame_height is not None and frame_height <= 0:
        raise ValueError("frame_height doit etre strictement positif")
    cache_key = f"strip:{name}|{frame_width}|{frame_height or 0}"
    cached = _STRIP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    image = _open_image(name)
    height = frame_height if frame_height is not None else image.height
    columns = image.width // frame_width
    if columns <= 0 or height > image.height:
        raise ValueError(f"bandeau '{name}' trop petit pour des frames {frame_width}x{height}")

    frames: list[arcade.Texture] = []
    for index in range(columns):
        left = index * frame_width
        crop = image.crop((left, 0, left + frame_width, height))
        texture_key = f"{cache_key}|{index}"
        frames.append(arcade.Texture(crop, hash=texture_key))
    strip = tuple(frames)
    _STRIP_CACHE[cache_key] = strip
    return strip


@dataclass(frozen=True, slots=True)
class StripAnimation:
    """Une sequence de frames a derouler a intervalle fixe."""

    textures: tuple[arcade.Texture, ...]
    frame_time: float
    loop: bool = True

    def __post_init__(self) -> None:
        if not self.textures:
            raise ValueError("textures ne doit pas etre vide")
        if self.frame_time <= 0:
            raise ValueError("frame_time doit etre strictement positif")


class Animator:
    """Curseur d'animation reutilisable (marche, disparition, plus tard ennemis)."""

    def __init__(
        self,
        animation: StripAnimation,
        speed: float = settings.ANIM_SPEED,
    ) -> None:
        if speed <= 0:
            raise ValueError("speed doit etre strictement positif")
        self._animation = animation
        self.speed = speed
        self.elapsed = 0.0
        self.finished = False

    @property
    def animation(self) -> StripAnimation:
        return self._animation

    def play(self, animation: StripAnimation) -> None:
        """Change d'animation. No-op si c'est deja celle en cours."""
        if animation is self._animation:
            return
        self._animation = animation
        self.elapsed = 0.0
        self.finished = False

    def update(self, delta_time: float) -> arcade.Texture:
        """Avance l'horloge et retourne la texture courante."""
        frames = self._animation.textures
        last_index = len(frames) - 1
        scaled = delta_time * self.speed
        if self._animation.loop:
            self.elapsed += scaled
            index = int(self.elapsed / self._animation.frame_time) % len(frames)
        elif not self.finished:
            self.elapsed += scaled
            index = min(int(self.elapsed / self._animation.frame_time), last_index)
            duration = self._animation.frame_time * len(frames)
            if self.elapsed >= duration:
                self.finished = True
                index = last_index
        else:
            index = last_index
        return frames[index]


def apply_facing(sprite: arcade.Sprite, facing: int) -> None:
    """Retourne le sprite horizontalement selon `facing` (-1 gauche, +1 droite)."""
    if facing == 0:
        return
    sign = 1 if facing > 0 else -1
    magnitude = abs(sprite.scale_x) if sprite.scale_x else 1.0
    sprite.scale_x = magnitude * sign


def scale_for_size(texture: arcade.Texture, size: float) -> float:
    """Facteur d'echelle pour que `texture` tienne dans un carre de `size` px."""
    if size <= 0:
        raise ValueError("size doit etre strictement positif")
    if texture.width <= 0:
        raise ValueError("texture.width doit etre strictement positif")
    return size / texture.width


def apply_rect_hit_box(
    sprite: arcade.Sprite,
    width: float,
    height: float,
    *,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> None:
    """Impose une hitbox rectangulaire, independante des pixels transparents.

    Les points sont en coordonnees locales (echelle 1) : a utiliser avec des
    textures deja redimensionnees a la taille voulue.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width et height doivent etre strictement positifs")
    half_width = width / 2
    half_height = height / 2
    points = (
        (-half_width + offset_x, -half_height + offset_y),
        (half_width + offset_x, -half_height + offset_y),
        (half_width + offset_x, half_height + offset_y),
        (-half_width + offset_x, half_height + offset_y),
    )
    sprite.hit_box = HitBox(points, position=sprite.position)


def _open_image(name: str) -> Image.Image:
    cached = _IMAGE_CACHE.get(name)
    if cached is not None:
        return cached
    path = sprite_path(name)
    if not path.is_file():
        raise FileNotFoundError(f"sprite introuvable : {path}")
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    _IMAGE_CACHE[name] = image
    return image


def _scale_overlay(image: Image.Image, size: int) -> Image.Image:
    """Redimensionne un overlay : carre -> carre ; sinon largeur = `size`, aligne en haut."""
    if image.size == (size, size):
        return image
    scale = size / image.width
    new_height = max(1, round(image.height * scale))
    scaled = image.resize((size, new_height), Image.Resampling.NEAREST)
    if new_height == size:
        return scaled
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(scaled, (0, 0), scaled)
    return canvas
