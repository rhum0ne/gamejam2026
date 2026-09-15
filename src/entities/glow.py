"""Halo additif doux, partage par le fantome et la trainee de dash."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager

import arcade
from arcade.types import Color, XYWH
from PIL import Image

_GLOW_RESOLUTION = 256
_TEXTURE: arcade.Texture | None = None


@contextmanager
def additive_blend() -> Iterator[None]:
    """Passe le blend en additif le temps d'une salve de halos."""
    ctx = arcade.get_window().ctx
    previous = ctx.blend_func
    ctx.blend_func = ctx.BLEND_ADDITIVE
    try:
        yield
    finally:
        ctx.blend_func = previous


def draw_glow(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    color: tuple[int, int, int],
    alpha: int,
    *,
    bind_blend: bool = True,
) -> None:
    """Dessine un blob lumineux centre sur `(center_x, center_y)`.

    Arcade `BLEND_ADDITIVE` est (ONE, ONE) : le degrade doit vivre dans le
    RGB (premultiplie), pas seulement dans l'alpha, sinon le halo est opaque.

    `bind_blend=False` suppose que l'appelant a deja ouvert `additive_blend`.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width et height doivent etre strictement positifs")
    opacity = max(0, min(255, int(alpha)))
    if opacity == 0:
        return
    if bind_blend:
        with additive_blend():
            _stamp_glow(center_x, center_y, width, height, color, opacity)
        return
    _stamp_glow(center_x, center_y, width, height, color, opacity)


def _stamp_glow(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    color: tuple[int, int, int],
    opacity: int,
) -> None:
    arcade.draw_texture_rect(
        _glow_texture(),
        XYWH(center_x, center_y, width, height),
        color=Color.from_iterable(color),
        alpha=opacity,
        pixelated=False,
    )


def _glow_texture() -> arcade.Texture:
    global _TEXTURE
    if _TEXTURE is None:
        _TEXTURE = _build_texture(_GLOW_RESOLUTION)
    return _TEXTURE


def _build_texture(size: int) -> arcade.Texture:
    """Degrade radial (1-t)^3, RGB premultiplie pour le blend additif."""
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
            falloff = rest * rest * rest
            value = int(255 * falloff)
            if value == 0:
                continue
            index = row + x * 4
            pixels[index] = value
            pixels[index + 1] = value
            pixels[index + 2] = value
            pixels[index + 3] = value
    image = Image.frombytes("RGBA", (size, size), bytes(pixels))
    return arcade.Texture(image, hash=f"entity-glow-premul-{size}")
