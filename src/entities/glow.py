"""Halo additif doux, partage par le fantome et la trainee de dash.

`draw_glow` en mode immediat (`arcade.draw_texture_rect`) coute un draw call
GPU par halo. `glow_pass` agrege les halos dans une `SpriteList`.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterator
from contextlib import contextmanager

import arcade
from arcade.types import Color, XYWH
from PIL import Image

import settings

_GLOW_RESOLUTION = 256
_TEXTURE: arcade.Texture | None = None
_BATCH: _GlowBatch | None = None
_BATCH_DEPTH = 0

_BATCH_CAPACITY = 2048


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


@contextmanager
def glow_pass() -> Iterator[None]:
    """Regroupe tous les `draw_glow` du bloc en un seul rendu SpriteList."""
    global _BATCH_DEPTH
    batch = _glow_batch()
    if _BATCH_DEPTH == 0:
        batch.begin()
    _BATCH_DEPTH += 1
    try:
        yield
    finally:
        _BATCH_DEPTH -= 1
        if _BATCH_DEPTH == 0:
            batch.flush()


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
    Dans un `glow_pass`, les halos sont stockes puis dessines en lot.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width et height doivent etre strictement positifs")
    opacity = max(0, min(255, int(alpha)))
    if opacity == 0:
        return
    if _BATCH_DEPTH > 0:
        _glow_batch().add(center_x, center_y, width, height, color, opacity)
        return
    if bind_blend:
        with additive_blend():
            _stamp_glow(center_x, center_y, width, height, color, opacity)
        return
    _stamp_glow(center_x, center_y, width, height, color, opacity)


def draw_threat_glow(
    center_x: float,
    center_y: float,
    *,
    bind_blend: bool = True,
) -> None:
    """Halo rouge des piques et des ennemis : meme couleur, meme taille.

    Dessine hors du champ de vision (au-dessus du voile) pour signaler
    la menace a travers le noir.
    """
    pulse = 1.0 + settings.HAZARD_GHOST_GLOW_PULSE * math.sin(
        time.perf_counter() * settings.HAZARD_GHOST_GLOW_PULSE_SPEED
        + center_x * 0.11
        + center_y * 0.07
    )
    size = settings.HAZARD_GHOST_GLOW_SIZE
    mid = settings.HAZARD_GHOST_GLOW_MID_SIZE
    inner = settings.HAZARD_GHOST_GLOW_INNER_SIZE
    draw_glow(
        center_x,
        center_y,
        size,
        size,
        settings.COLOR_HAZARD_GLOW,
        min(255, int(settings.HAZARD_GHOST_GLOW_ALPHA * pulse)),
        bind_blend=bind_blend,
    )
    draw_glow(
        center_x,
        center_y,
        mid,
        mid,
        settings.COLOR_HAZARD_GLOW,
        min(255, int(settings.HAZARD_GHOST_GLOW_MID_ALPHA * pulse)),
        bind_blend=bind_blend,
    )
    draw_glow(
        center_x,
        center_y,
        inner,
        inner,
        settings.COLOR_HAZARD_GLOW_CORE,
        min(255, int(settings.HAZARD_GHOST_GLOW_INNER_ALPHA * pulse)),
        bind_blend=bind_blend,
    )


class _GlowBatch:
    """Sprites de halo reutilises d'une frame a l'autre."""

    def __init__(self) -> None:
        self._sprites: arcade.SpriteList = arcade.SpriteList(
            use_spatial_hash=False,
            capacity=_BATCH_CAPACITY,
        )
        self._count = 0

    def begin(self) -> None:
        self._count = 0

    def add(
        self,
        center_x: float,
        center_y: float,
        width: float,
        height: float,
        color: tuple[int, int, int],
        opacity: int,
    ) -> None:
        if self._count >= len(self._sprites):
            sprite = arcade.Sprite(_glow_texture(), center_x=center_x, center_y=center_y)
            self._sprites.append(sprite)
        else:
            sprite = self._sprites[self._count]
            sprite.center_x = center_x
            sprite.center_y = center_y
        sprite.angle = 0.0
        sprite.visible = True
        sprite.width = width
        sprite.height = height
        sprite.color = Color(color[0], color[1], color[2], opacity)
        self._count += 1

    def flush(self) -> None:
        sprites = self._sprites
        if self._count <= 0:
            for sprite in sprites:
                sprite.visible = False
            return
        extra = len(sprites) - self._count
        if extra > 64:
            for _ in range(extra):
                sprites.pop()
        else:
            for index in range(self._count, len(sprites)):
                sprites[index].visible = False
        with additive_blend():
            sprites.draw(pixelated=False)


def _glow_batch() -> _GlowBatch:
    global _BATCH
    if _BATCH is None:
        _BATCH = _GlowBatch()
    return _BATCH


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
