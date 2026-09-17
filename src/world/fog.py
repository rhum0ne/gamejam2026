"""Voile de vision du fantome : degrade radial noir -> transparent.

Le rayon du degrade suit `Ghost.vision_radius` (bonus des paliers
`vision_*`, puis reduction au fil du timer). L'opacite maximale vient de
`settings.FOG_ALPHA`. La texture est construite une seule fois et seulement
mise a l'echelle a l'affichage.

`draw` reste le chemin du jeu (un seul centre). `draw_many` superpose
plusieurs halos avec le meme falloff, pour le decor du menu.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from textwrap import dedent

import arcade
from arcade.camera import Camera2D
from arcade.gl import geometry
from arcade.types import XYWH
from PIL import Image

import settings

_MAX_LIGHTS = 8

_MULTI_VERTEX = dedent(
    """\
    #version 330

    in vec2 in_vert;
    in vec2 in_uv;
    out vec2 v_uv;

    void main() {
        gl_Position = vec4(in_vert, 0.0, 1.0);
        v_uv = in_uv;
    }
    """
)

_MULTI_FRAGMENT = dedent(
    """\
    #version 330

    uniform vec4 u_view;
    uniform float u_fog_alpha;
    uniform float u_clear_ratio;
    uniform float u_falloff_power;
    uniform int u_count;
    uniform vec3 u_light0;
    uniform vec3 u_light1;
    uniform vec3 u_light2;
    uniform vec3 u_light3;
    uniform vec3 u_light4;
    uniform vec3 u_light5;
    uniform vec3 u_light6;
    uniform vec3 u_light7;

    in vec2 v_uv;
    out vec4 frag_color;

    float veil_for(vec2 world, vec3 light) {
        float radius = max(light.z, 1.0);
        float dist = distance(world, light.xy);
        if (dist >= radius) {
            return 1.0;
        }
        float inner = clamp(u_clear_ratio, 0.0, 0.95) * radius;
        if (dist <= inner) {
            return 0.0;
        }
        float t = (dist - inner) / max(radius - inner, 1.0);
        return pow(t, max(u_falloff_power, 1.0));
    }

    void main() {
        vec2 world = vec2(
            mix(u_view.x, u_view.y, v_uv.x),
            mix(u_view.z, u_view.w, v_uv.y)
        );
        vec3 lights[8];
        lights[0] = u_light0;
        lights[1] = u_light1;
        lights[2] = u_light2;
        lights[3] = u_light3;
        lights[4] = u_light4;
        lights[5] = u_light5;
        lights[6] = u_light6;
        lights[7] = u_light7;
        float veil = 1.0;
        int count = clamp(u_count, 0, 8);
        if (0 < count) { veil = min(veil, veil_for(world, lights[0])); }
        if (1 < count) { veil = min(veil, veil_for(world, lights[1])); }
        if (2 < count) { veil = min(veil, veil_for(world, lights[2])); }
        if (3 < count) { veil = min(veil, veil_for(world, lights[3])); }
        if (4 < count) { veil = min(veil, veil_for(world, lights[4])); }
        if (5 < count) { veil = min(veil, veil_for(world, lights[5])); }
        if (6 < count) { veil = min(veil, veil_for(world, lights[6])); }
        if (7 < count) { veil = min(veil, veil_for(world, lights[7])); }
        frag_color = vec4(0.0, 0.0, 0.0, u_fog_alpha * veil);
    }
    """
)


class GhostFog:
    """Overlay plein ecran : noir hors du champ, transparent au centre du fantome."""

    def __init__(self, resolution: int = 256) -> None:
        self._resolution = max(32, resolution)
        self._fog_alpha = settings.FOG_ALPHA
        self._clear_ratio = settings.GHOST_VISION_CLEAR_RATIO
        self._falloff_power = settings.GHOST_VISION_FALLOFF_POWER
        self._texture = self._build_texture()
        self._multi_program = None
        self._multi_quad = None

    def draw(self, ghost: arcade.Sprite, camera: Camera2D) -> None:
        """Dessine le voile centre sur `ghost`, taille = 2 * vision_radius."""
        radius = max(1.0, float(getattr(ghost, "vision_radius", settings.GHOST_VISION_RADIUS)))
        self.draw_at(ghost.center_x, ghost.center_y, radius, camera)

    def draw_at(
        self, center_x: float, center_y: float, radius: float, camera: Camera2D
    ) -> None:
        """Voile centre sur un point, meme si le fantome n'existe plus."""
        radius = max(1.0, radius)
        self._draw_outside(center_x, center_y, radius, camera)
        arcade.draw_texture_rect(
            self._texture,
            XYWH(center_x, center_y, radius * 2, radius * 2),
        )

    def draw_many(self, ghosts: Sequence[arcade.Sprite], camera: Camera2D) -> None:
        """Superpose un halo par fantome, meme courbe que `draw`."""
        if not ghosts:
            self._draw_full(camera)
            return
        program = self._multi_shader()
        if program is None:
            self.draw(ghosts[0], camera)
            return
        cam_x, cam_y = camera.position
        half_w = camera.width / 2
        half_h = camera.height / 2
        program["u_view"] = cam_x - half_w, cam_x + half_w, cam_y - half_h, cam_y + half_h
        program["u_fog_alpha"] = max(0, min(255, self._fog_alpha)) / 255.0
        program["u_clear_ratio"] = self._clear_ratio
        program["u_falloff_power"] = self._falloff_power
        visible = list(ghosts)[:_MAX_LIGHTS]
        program["u_count"] = len(visible)
        for index in range(_MAX_LIGHTS):
            if index < len(visible):
                ghost = visible[index]
                radius = max(
                    1.0,
                    float(getattr(ghost, "vision_radius", settings.GHOST_VISION_RADIUS)),
                )
                program[f"u_light{index}"] = ghost.center_x, ghost.center_y, radius
            else:
                program[f"u_light{index}"] = 0.0, 0.0, 1.0
        # Sans blend, le quad ecrase le monde en noir opaque : on ne voit plus
        # que les sprites dessines apres (les fantomes). Arcade peut couper le
        # blend en sortant d'une SpriteList, il faut le forcer ici.
        ctx = arcade.get_window().ctx
        ctx.enable(ctx.BLEND)
        previous = ctx.blend_func
        ctx.blend_func = ctx.BLEND_DEFAULT
        try:
            self._multi_quad.render(program)
        finally:
            ctx.blend_func = previous

    def _multi_shader(self):
        """Compile le shader multi-halos une fois, des qu'une fenetre existe."""
        if self._multi_program is not None:
            return self._multi_program
        window = arcade.get_window()
        self._multi_program = window.ctx.program(
            vertex_shader=_MULTI_VERTEX,
            fragment_shader=_MULTI_FRAGMENT,
        )
        self._multi_quad = geometry.quad_2d_fs()
        return self._multi_program

    def _draw_full(self, camera: Camera2D) -> None:
        cam_x, cam_y = camera.position
        half_w = camera.width / 2
        half_h = camera.height / 2
        arcade.draw_lrbt_rectangle_filled(
            cam_x - half_w,
            cam_x + half_w,
            cam_y - half_h,
            cam_y + half_h,
            (0, 0, 0, settings.FOG_ALPHA),
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
        power = max(1.0, self._falloff_power)
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
                    alpha = int(fog_alpha * (t ** power))
                index = row + x * 4
                pixels[index + 3] = alpha
        image = Image.frombytes("RGBA", (size, size), bytes(pixels))
        return arcade.Texture(
            image,
            hash=f"ghost-fog-{size}-{fog_alpha}-{self._clear_ratio:.3f}-{power:.2f}",
        )
