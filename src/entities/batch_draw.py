"""Lots SpriteList reutilisables : quads colores et sous-ensembles de sprites.

Arcade 3.3 dessine les sprites par batch GPU (`SpriteList`) et ignore ceux
hors viewport. `arcade.draw_point` / `arcade.draw_sprite` en mode immediat
coutent un draw call chacun : les trainees et poussieres passent donc ici.
"""

from __future__ import annotations

from collections.abc import Sequence

import arcade
from arcade.types import Color
from PIL import Image

_WHITE: arcade.Texture | None = None


def white_quad_texture() -> arcade.Texture:
    """Carre blanc 2x2, teinte ensuite via `Sprite.color`."""
    global _WHITE
    if _WHITE is None:
        image = Image.new("RGBA", (2, 2), (255, 255, 255, 255))
        _WHITE = arcade.Texture(image, hash="quad-batch-white-2")
    return _WHITE


class QuadBatch:
    """Sprites carres recycles, un seul `SpriteList.draw` par flush."""

    def __init__(self, capacity: int = 256) -> None:
        if capacity < 1:
            raise ValueError("capacity doit etre >= 1")
        self._sprites: arcade.SpriteList = arcade.SpriteList(
            use_spatial_hash=False,
            capacity=capacity,
            lazy=True,
        )
        self._count = 0

    def begin(self) -> None:
        self._count = 0

    def add(
        self,
        center_x: float,
        center_y: float,
        size: float,
        color: tuple[int, int, int],
        alpha: int,
    ) -> None:
        opacity = max(0, min(255, int(alpha)))
        if opacity <= 0 or size <= 0:
            return
        if self._count >= len(self._sprites):
            sprite = arcade.Sprite(
                white_quad_texture(),
                center_x=center_x,
                center_y=center_y,
            )
            self._sprites.append(sprite)
        else:
            sprite = self._sprites[self._count]
            sprite.center_x = center_x
            sprite.center_y = center_y
        sprite.visible = True
        sprite.width = size
        sprite.height = size
        sprite.color = Color(color[0], color[1], color[2], opacity)
        self._count += 1

    def flush(self, *, pixelated: bool = True) -> None:
        sprites = self._sprites
        if self._count <= 0:
            return
        extra = len(sprites) - self._count
        if extra > 64:
            for _ in range(extra):
                sprites.pop()
        else:
            for index in range(self._count, len(sprites)):
                sprites[index].visible = False
        sprites.draw(pixelated=pixelated)


class SpriteOverlay:
    """Redessine un sous-ensemble de sprites (deja dans d'autres listes)."""

    def __init__(self, capacity: int = 256) -> None:
        self._list = arcade.SpriteList(use_spatial_hash=False, capacity=capacity, lazy=True)
        self._last: tuple[int, ...] = ()

    def draw(
        self,
        sprites: Sequence[arcade.Sprite],
        *,
        pixelated: bool = False,
    ) -> None:
        wanted = tuple(sprites)
        if not wanted:
            return
        keys = tuple(id(sprite) for sprite in wanted)
        if keys != self._last:
            self._list.clear()
            for sprite in wanted:
                self._list.append(sprite)
            self._last = keys
        self._list.draw(pixelated=pixelated)
