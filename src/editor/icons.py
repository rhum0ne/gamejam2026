"""Textures d'affichage de l'editeur, generees une fois et mises en cache.

Le terrain reutilise les textures du jeu (`obstacles.terrain_texture`) : ce que
le level designer voit dans l'editeur est exactement ce que le joueur verra.
Les elements sans sprite (porte, ennemi, ...) recoivent un carre
colore avec leur symbole de legende grave dedans : c'est lisible, et surtout
c'est une texture, donc le rendu reste un seul batch de `SpriteList`.
"""

from __future__ import annotations

import arcade
from PIL import Image, ImageDraw, ImageFont

import settings
from src.editor.palette import PaletteItem
from src.ui import sprites
from src.world.decorations import DECORATION_SPECS, decoration_spec
from src.world.obstacles import terrain_texture
from src.world.spring import spring_texture

_CACHE: dict[tuple[str, int], arcade.Texture] = {}
_GLYPH_CANVAS = (12, 14)  # taille de rendu de la police bitmap par defaut

_SPRITE_KINDS = {
    "flamethrower": settings.SPRITE_FLAMETHROWER,
    "checkpoint": settings.SPRITE_CHECKPOINT,
}


def cell_texture(item: PaletteItem, size: int) -> arcade.Texture:
    """Texture carree de `size` px representant `item`."""
    if size <= 0:
        raise ValueError("size doit etre strictement positif")
    key = (item.kind, size)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    spec = item.spec
    if spec is None:
        sprite_name = _SPRITE_KINDS.get(item.kind)
        if item.kind in DECORATION_SPECS:
            texture = _decoration_swatch(item.kind, size)
        elif item.kind == settings.TILE_KIND_SPRING:
            texture = spring_texture(size)
        elif sprite_name is not None:
            texture = sprites.load_texture(sprite_name, size=size)
        else:
            texture = _placeholder(item, size)
    elif spec.role == "spike":
        texture = sprites.load_texture(spec.sprite, size=size)
    else:
        texture = terrain_texture(spec, size)
    _CACHE[key] = texture
    return texture


def _decoration_swatch(kind: str, size: int) -> arcade.Texture:
    """Vignette carree : le prop garde son ratio, pose en bas de la case."""
    spec = decoration_spec(kind)
    source = sprites.load_sheet_region(spec.sheet, spec.box).image
    scale = min(size / source.width, size / source.height)
    width = max(1, round(source.width * scale))
    height = max(1, round(source.height * scale))
    fitted = source.resize((width, height), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(fitted, ((size - width) // 2, size - height), fitted)
    return arcade.Texture(canvas, hash=f"editor-decor-{kind}-{size}")


def _placeholder(item: PaletteItem, size: int) -> arcade.Texture:
    """Carre colore + symbole, pour un element de gameplay sans sprite."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = max(1, size // 12)
    draw.rectangle(
        (inset, inset, size - inset - 1, size - inset - 1),
        fill=(*item.color, 232),
        outline=(*_shade(item.color, 1.45), 255),
        width=max(1, size // 16),
    )
    glyph = _glyph(item.symbol, size, _shade(item.color, 0.25))
    if glyph is not None:
        left = (size - glyph.width) // 2
        top = (size - glyph.height) // 2
        image.alpha_composite(glyph, (left, top))
    return arcade.Texture(image, hash=f"editor-cell-{item.kind}-{size}")


def _glyph(symbol: str, size: int, color: tuple[int, int, int]) -> Image.Image | None:
    """Rend le premier caractere de `symbol` en gros, ou None s'il est vide."""
    if not symbol:
        return None
    canvas = Image.new("RGBA", _GLYPH_CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((1, 1), symbol[0], font=ImageFont.load_default(), fill="white")
    box = canvas.getbbox()
    if box is None:
        return None
    cropped = canvas.crop(box)
    target = max(1, int(size * 0.52))
    scale = target / max(cropped.width, cropped.height)
    scaled = cropped.resize(
        (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))),
        Image.Resampling.NEAREST,
    )
    tinted = Image.new("RGBA", scaled.size, (*color, 255))
    tinted.putalpha(scaled.getchannel("A"))
    return tinted


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """Eclaircit (`factor` > 1) ou assombrit (`factor` < 1) une couleur."""
    return tuple(max(0, min(255, int(channel * factor))) for channel in color)  # type: ignore[return-value]
