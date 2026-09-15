"""Chargement, cache et composition des textures.

Module feuille : n'importe que `arcade` et `settings`. Les tuiles, et plus
tard les entites / objets, passent par ici pour recuperer un sprite plutot
que de recharger un PNG a chaque construction.

Les images natives font 16 px ; on les agrandit en nearest-neighbor jusqu'a
`TILE_SIZE` pour garder le pixel art net.
"""

from __future__ import annotations

from pathlib import Path

import arcade
from arcade.hitbox import HitBox
from PIL import Image

import settings

_IMAGE_CACHE: dict[str, Image.Image] = {}
_TEXTURE_CACHE: dict[str, arcade.Texture] = {}


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
