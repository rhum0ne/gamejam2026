"""Voile de vision du fantome : degrade radial noir -> transparent.

Le rayon du degrade suit `Ghost.vision_radius` (donc les ameliorations
`vision_*` de l'arbre de competences). L'opacite maximale vient de
`settings.FOG_ALPHA`. La texture est construite une seule fois et seulement
mise a l'echelle a l'affichage.
"""

from __future__ import annotations

import math

import arcade
from arcade.camera import Camera2D
from arcade.types import XYWH
from PIL import Image

import settings


class GhostFog:
    """Overlay plein ecran : noir hors du champ, transparent au centre du fantome."""

    def __init__(self, resolution: int = 256) -> None:
        self._resolution = max(32, resolution)
        self._fog_alpha = settings.FOG_ALPHA
        self._clear_ratio = settings.GHOST_VISION_CLEAR_RATIO
        self._texture = self._build_texture()

    def draw(self, ghost: arcade.Sprite, camera: Camera2D) -> None:
        """Dessine le voile centre sur `ghost`, taille = 2 * vision_radius."""
        radius = max(1.0, float(getattr(ghost, "vision_radius", settings.GHOST_VISION_RADIUS)))
        self._draw_outside(ghost.center_x, ghost.center_y, radius, camera)
        arcade.draw_texture_rect(
            self._texture,
            XYWH(ghost.center_x, ghost.center_y, radius * 2, radius * 2),
        )

    def _draw_outside(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        camera: Camera2D,
    ) -> None:
        """Remplit de noir tout le viewport sauf le carre du degrade."""
        cam_x, cam_y = camera.position
        half_w = camera.width / 2
        half_h = camera.height / 2
        view_left = cam_x - half_w
        view_right = cam_x + half_w
        view_bottom = cam_y - half_h
        view_top = cam_y + half_h
        box_left = center_x - radius
        box_right = center_x + radius
        box_bottom = center_y - radius
        box_top = center_y + radius
        fog = (0, 0, 0, settings.FOG_ALPHA)

        if view_left < box_left:
            arcade.draw_lrbt_rectangle_filled(view_left, box_left, view_bottom, view_top, fog)
        if view_right > box_right:
            arcade.draw_lrbt_rectangle_filled(box_right, view_right, view_bottom, view_top, fog)
        strip_left = max(view_left, box_left)
        strip_right = min(view_right, box_right)
        if strip_left < strip_right:
            if view_bottom < box_bottom:
                arcade.draw_lrbt_rectangle_filled(
                    strip_left, strip_right, view_bottom, box_bottom, fog
                )
            if view_top > box_top:
                arcade.draw_lrbt_rectangle_filled(
                    strip_left, strip_right, box_top, view_top, fog
                )

    def _build_texture(self) -> arcade.Texture:
        size = self._resolution
        radius = size / 2
        inner = max(0.0, min(0.95, self._clear_ratio)) * radius
        fade_span = max(1.0, radius - inner)
        pixels = bytearray(size * size * 4)
        fog_alpha = max(0, min(255, self._fog_alpha))
        for y in range(size):
            dy = y + 0.5 - radius
            row = y * size * 4
            for x in range(size):
                dist = math.hypot(x + 0.5 - radius, dy)
                if dist >= radius:
                    alpha = fog_alpha
                elif dist <= inner:
                    alpha = 0
                else:
                    t = (dist - inner) / fade_span
                    t = t * t * (3.0 - 2.0 * t)
                    alpha = int(fog_alpha * t)
                index = row + x * 4
                pixels[index + 3] = alpha
        image = Image.frombytes("RGBA", (size, size), bytes(pixels))
        return arcade.Texture(
            image,
            hash=f"ghost-fog-{size}-{fog_alpha}-{self._clear_ratio:.3f}",
        )
