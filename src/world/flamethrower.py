"""Lance-flammes : buse sprite + jet procedural (un quad, un shader).

Le jet est volontairement cheap : un triangle-strip, des braises circulaires
hachees dans le fragment, blend additif. Pas de systeme de particules CPU.

Configurable par instance (carte JSON / editeur) : portee en tuiles, periode
d'allumage, direction (4 axes). La hitbox suit le quad du jet et tue corps
et ennemis. Le jet part de la face avant de la tuile, pas du centre du sprite.
"""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent

import arcade
from arcade.gl import geometry

import settings
from src.entities.glow import additive_blend, draw_threat_glow
from src.ui import sprites

DIRECTION_CYCLE = ("right", "down", "left", "up")
DIRECTION_VECTOR = {
    "right": (1.0, 0.0),
    "down": (0.0, -1.0),
    "left": (-1.0, 0.0),
    "up": (0.0, 1.0),
}
DIRECTION_ANGLE = {
    "right": 0.0,
    "up": 90.0,
    "left": 180.0,
    "down": -90.0,
}
DIRECTION_ARROW = {
    "right": ">",
    "down": "v",
    "left": "<",
    "up": "^",
}
DIRECTION_LABEL = {
    "right": "droite",
    "down": "bas",
    "left": "gauche",
    "up": "haut",
}

_VERTEX_SHADER = dedent(
    """\
    #version 330

    uniform vec2 u_origin;
    uniform vec2 u_size;
    uniform vec2 u_dir;
    uniform vec4 u_view;
    uniform float u_pad;

    in vec2 in_vert;
    in vec2 in_uv;
    out vec2 v_uv;

    void main() {
        vec2 perp = vec2(-u_dir.y, u_dir.x);
        float pad_back = u_pad * 0.2;
        float along_world = in_uv.x * (u_size.x + pad_back + u_pad) - pad_back;
        float across_world = (in_uv.y - 0.5) * (u_size.y + 2.0 * u_pad);
        vec2 world = u_origin + u_dir * along_world + perp * across_world;
        float nx = (world.x - u_view.x) / max(u_view.y - u_view.x, 0.0001);
        float ny = (world.y - u_view.z) / max(u_view.w - u_view.z, 0.0001);
        gl_Position = vec4(nx * 2.0 - 1.0, ny * 2.0 - 1.0, 0.0, 1.0);
        v_uv = vec2(along_world / max(u_size.x, 0.0001),
                    across_world / max(u_size.y, 0.0001) + 0.5);
        v_uv += in_vert * 0.0;
    }
    """
)

_FRAGMENT_SHADER = dedent(
    """\
    #version 330

    uniform float u_time;
    uniform float u_intensity;
    uniform float u_seed;
    uniform float u_aspect;
    in vec2 v_uv;
    out vec4 frag_color;

    float hash(float n) {
        return fract(sin(n) * 43758.5453);
    }

    float sd_capsule(vec2 p, vec2 a, vec2 b, float radius) {
        vec2 pa = p - a;
        vec2 ba = b - a;
        float h = clamp(dot(pa, ba) / max(dot(ba, ba), 0.0001), 0.0, 1.0);
        return length(pa - ba * h) - radius;
    }

    float blob(vec2 uv, vec2 pos, float radius) {
        vec2 d = uv - pos;
        d.x *= u_aspect;
        return 1.0 - smoothstep(radius * 0.30, radius, length(d));
    }

    void main() {
        float along = v_uv.x;
        float across = v_uv.y * 2.0 - 1.0;
        float len = max(u_aspect * 2.0, 0.001);
        float radius = 0.88;
        vec2 p = vec2(along * len, across);
        vec2 cap_a = vec2(radius, 0.0);
        vec2 cap_b = vec2(max(len - radius, radius), 0.0);
        float sd = sd_capsule(p, cap_a, cap_b, radius);

        float body = 1.0 - smoothstep(-0.06, 0.10, sd);
        float halo = 1.0 - smoothstep(0.0, 0.28, sd);
        float inner = 1.0 - smoothstep(-0.22, 0.02, sd + 0.32);
        if (halo <= 0.02 && body <= 0.02) {
            discard;
        }

        float embers = 0.0;
        for (int i = 0; i < 10; i++) {
            float id = float(i) + u_seed;
            float rnd = hash(id * 3.17);
            float rnd2 = hash(id * 5.91);
            float life = fract(u_time * (0.32 + rnd * 0.48) + rnd);
            float px = 0.06 + life * 0.88;
            float py = 0.5 + (rnd2 - 0.5) * 0.42;
            py += sin(u_time * 3.2 + rnd * 6.28) * 0.04;
            float rad = mix(0.26, 0.15, life) * (0.85 + rnd * 0.3);
            embers += blob(v_uv, vec2(px, py), rad) * mix(0.85, 0.45, life);
        }
        for (int i = 0; i < 8; i++) {
            float id = float(i) + 29.0 + u_seed;
            float rnd = hash(id * 1.37);
            float rnd2 = hash(id * 8.21);
            float life = fract(u_time * (0.7 + rnd * 1.1) + rnd2);
            float px = 0.08 + life * 0.84;
            float py = 0.5 + (rnd2 - 0.5) * 0.50;
            embers += blob(v_uv, vec2(px, py), mix(0.10, 0.05, life)) * (1.0 - life);
        }
        embers = clamp(embers, 0.0, 1.15) * inner;

        float heat = body * mix(0.42, 0.78, inner) + embers * 0.55 + inner * 0.22;
        heat = clamp(heat, 0.0, 1.35) * u_intensity;
        float alpha = max(body, halo * 0.45) * u_intensity;
        if (alpha <= 0.02) {
            discard;
        }

        vec3 cool = vec3(0.50, 0.04, 0.00);
        vec3 mid = vec3(1.00, 0.40, 0.05);
        vec3 hot = vec3(1.00, 0.92, 0.52);
        vec3 color = mix(cool, mid, smoothstep(0.12, 0.55, heat));
        color = mix(color, hot, smoothstep(0.52, 1.10, heat));
        frag_color = vec4(color * alpha, alpha);
    }
    """
)

_PROGRAM = None
_QUAD = None


@dataclass(frozen=True, slots=True)
class FlameSpec:
    """Reglages d'un lance-flammes, en coordonnees de grille."""

    column: int
    row: int
    range_tiles: int = settings.FLAMETHROWER_RANGE
    interval: float = settings.FLAMETHROWER_INTERVAL
    direction: str = "right"

    def __post_init__(self) -> None:
        if self.column < 0 or self.row < 0:
            raise ValueError("column et row doivent etre positifs")
        object.__setattr__(self, "range_tiles", _clamp_range(self.range_tiles))
        object.__setattr__(self, "interval", _clamp_interval(self.interval))
        object.__setattr__(self, "direction", _normalize_direction(self.direction))

    def with_range(self, range_tiles: int) -> "FlameSpec":
        return FlameSpec(self.column, self.row, range_tiles, self.interval, self.direction)

    def with_interval(self, interval: float) -> "FlameSpec":
        return FlameSpec(self.column, self.row, self.range_tiles, interval, self.direction)

    def rotated(self) -> "FlameSpec":
        index = DIRECTION_CYCLE.index(self.direction)
        nxt = DIRECTION_CYCLE[(index + 1) % len(DIRECTION_CYCLE)]
        return FlameSpec(self.column, self.row, self.range_tiles, self.interval, nxt)

    def to_json(self) -> dict:
        return {
            "x": self.column,
            "y": self.row,
            "range": self.range_tiles,
            "interval": self.interval,
            "dir": self.direction,
        }


class Flamethrower(arcade.Sprite):
    """Buse fixe. Le jet n'est pas un sprite : shader + hitbox calculee."""

    lethal_for_body = False
    lethal_for_ghost = False

    def __init__(
        self,
        center_x: float,
        center_y: float,
        *,
        size: int = settings.TILE_SIZE,
        range_tiles: int = settings.FLAMETHROWER_RANGE,
        interval: float = settings.FLAMETHROWER_INTERVAL,
        direction: str = "right",
    ) -> None:
        texture = sprites.load_texture(settings.SPRITE_FLAMETHROWER, size=size)
        super().__init__(
            texture,
            scale=sprites.scale_for_size(texture, size),
            center_x=center_x,
            center_y=center_y,
        )
        self.range_tiles = _clamp_range(range_tiles)
        self.interval = _clamp_interval(interval)
        self.direction = _normalize_direction(direction)
        aim_sprite(self, self.direction)
        sprites.apply_rect_hit_box(self, size * 0.7, size * 0.55)
        self._age = (center_x * 0.013 + center_y * 0.021) % max(self.interval, 0.001)
        self.intensity = 0.0
        self._tile_size = size
        self._seed = (center_x * 0.07 + center_y * 0.11) % 32.0
        # True par defaut : un lance-flammes non lie crache selon son cycle.
        self.commanded_on = True
        # Lie a un activateur : plus de periode interne, allume ou eteint.
        self.activator_driven = False

    @property
    def is_lethal(self) -> bool:
        if not self.sprite_lists:
            return False
        return self.intensity >= settings.FLAMETHROWER_LETHAL_INTENSITY

    @property
    def flame_length(self) -> float:
        return self.range_tiles * self._tile_size

    def nozzle(self) -> tuple[float, float]:
        """Face avant de la tuile : le jet part d'ici, pas du centre du sprite."""
        return flame_start(self.center_x, self.center_y, self.direction, self._tile_size)

    def flame_bounds(self) -> tuple[float, float, float, float]:
        """Rectangle monde (gauche, droite, bas, haut) du jet."""
        origin_x, origin_y = self.nozzle()
        return flame_aabb(
            origin_x,
            origin_y,
            self.direction,
            self.flame_length,
            settings.FLAMETHROWER_HEIGHT,
        )

    def flame_midpoint(self) -> tuple[float, float]:
        left, right, bottom, top = self.flame_bounds()
        return (left + right) / 2, (bottom + top) / 2

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        dt = max(0.0, delta_time)
        if self.activator_driven:
            self._sync_gated_intensity()
            return
        self._age += dt
        self.intensity = _cycle_intensity(self._age, self.interval)

    def bind_to_activator(self) -> None:
        """Ignore le cycle interne : l'activateur decide allume / eteint."""
        self.activator_driven = True
        self._sync_gated_intensity()

    def set_commanded(self, on: bool) -> None:
        """Allume ou coupe le jet, sans retirer la buse du niveau."""
        self.commanded_on = bool(on)
        self.activator_driven = True
        self._sync_gated_intensity()

    def _sync_gated_intensity(self) -> None:
        if self.commanded_on and self.sprite_lists:
            self.intensity = 1.0
        else:
            self.intensity = 0.0

    def overlaps(self, sprite: arcade.Sprite) -> bool:
        """Le sprite chevauche-t-il le jet allume ?"""
        if not self.is_lethal:
            return False
        left, right, bottom, top = self.flame_bounds()
        return (
            sprite.right > left
            and sprite.left < right
            and sprite.top > bottom
            and sprite.bottom < top
        )

    def draw_flame(self) -> None:
        if not self.sprite_lists or self.intensity <= 0.01:
            return
        origin_x, origin_y = self.nozzle()
        _draw_flame_quad(
            origin_x,
            origin_y,
            self.flame_length,
            settings.FLAMETHROWER_HEIGHT,
            self.direction,
            self.intensity,
            self._age,
            self._seed,
        )

    def draw_ghost_glow(self, *, bind_blend: bool = True) -> None:
        """Le lance-flammes est une menace : halo rouge, plus le jet s'il crache."""
        draw_threat_glow(self.center_x, self.center_y, bind_blend=bind_blend)
        if self.is_lethal:
            mid_x, mid_y = self.flame_midpoint()
            draw_threat_glow(mid_x, mid_y, bind_blend=bind_blend)


def aim_sprite(sprite: arcade.Sprite, direction: str) -> None:
    """Oriente le sprite de buse selon un des 4 axes."""
    direction = _normalize_direction(direction)
    magnitude = abs(sprite.scale_x) if sprite.scale_x else 1.0
    sprite.scale_x = magnitude
    sprite.angle = DIRECTION_ANGLE[direction]


def flame_start(
    center_x: float,
    center_y: float,
    direction: str,
    tile_size: float,
) -> tuple[float, float]:
    """Point d'emission : face de la tuile dans la direction du jet."""
    dx, dy = DIRECTION_VECTOR[_normalize_direction(direction)]
    offset = tile_size * settings.FLAMETHROWER_NOZZLE
    return center_x + dx * offset, center_y + dy * offset


def flame_aabb(
    origin_x: float,
    origin_y: float,
    direction: str,
    length: float,
    thickness: float,
) -> tuple[float, float, float, float]:
    """AABB du jet partant de la buse selon `direction`."""
    dx, dy = DIRECTION_VECTOR[_normalize_direction(direction)]
    half = thickness / 2.0
    end_x = origin_x + dx * length
    end_y = origin_y + dy * length
    if abs(dx) >= abs(dy):
        left, right = min(origin_x, end_x), max(origin_x, end_x)
        bottom, top = origin_y - half, origin_y + half
    else:
        left, right = origin_x - half, origin_x + half
        bottom, top = min(origin_y, end_y), max(origin_y, end_y)
    return left, right, bottom, top


def parse_flame_specs(raw: object) -> dict[tuple[int, int], FlameSpec]:
    """Lit le champ `flamethrowers` d'une carte, ou {} s'il est absent."""
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError("flamethrowers doit etre une liste")
    specs: dict[tuple[int, int], FlameSpec] = {}
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"flamethrowers[{index}] doit etre un objet")
        try:
            spec = FlameSpec(
                column=_as_int(entry.get("x"), "x"),
                row=_as_int(entry.get("y"), "y"),
                range_tiles=_as_int(entry.get("range", settings.FLAMETHROWER_RANGE), "range"),
                interval=_as_float(
                    entry.get("interval", settings.FLAMETHROWER_INTERVAL), "interval"
                ),
                direction=_direction_from_entry(entry),
            )
        except ValueError as error:
            raise ValueError(f"flamethrowers[{index}] : {error}") from error
        specs[(spec.column, spec.row)] = spec
    return specs


def dump_flame_specs(specs: dict[tuple[int, int], FlameSpec]) -> list[dict]:
    """Serialise les lance-flammes, tries par position."""
    return [specs[key].to_json() for key in sorted(specs)]


def _normalize_direction(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("dir doit etre right, down, left ou up")
    key = value.strip().lower()
    if key not in DIRECTION_VECTOR:
        raise ValueError(f"dir inconnu : {value!r}")
    return key


def _direction_from_entry(entry: dict) -> str:
    if "dir" in entry:
        return _normalize_direction(entry["dir"])
    if "facing" in entry:
        facing = _as_int(entry["facing"], "facing")
        return "left" if facing < 0 else "right"
    return "right"


def _clamp_range(value: int) -> int:
    return max(settings.FLAMETHROWER_RANGE_MIN, min(settings.FLAMETHROWER_RANGE_MAX, int(value)))


def _clamp_interval(value: float) -> float:
    if value <= settings.FLAMETHROWER_ALWAYS_ON:
        return 0.0
    return max(
        settings.FLAMETHROWER_INTERVAL_MIN,
        min(settings.FLAMETHROWER_INTERVAL_MAX, float(value)),
    )


def _cycle_intensity(age: float, interval: float) -> float:
    if interval <= settings.FLAMETHROWER_ALWAYS_ON:
        return 1.0
    period = max(interval, 0.001)
    cycle = age % period
    on_time = max(0.05, min(period * 0.95, period * settings.FLAMETHROWER_ON_RATIO))
    if cycle >= on_time:
        return 0.0
    ramp = min(settings.FLAMETHROWER_RAMP, on_time * 0.45)
    if ramp <= 0.0:
        return 1.0
    rise = min(1.0, cycle / ramp)
    fade = min(1.0, (on_time - cycle) / ramp)
    return min(rise, fade)


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} doit etre un entier")
    return value


def _as_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} doit etre un nombre")
    return float(value)


def _draw_flame_quad(
    origin_x: float,
    origin_y: float,
    length: float,
    height: float,
    direction: str,
    intensity: float,
    time_value: float,
    seed: float,
) -> None:
    if length <= 0.0 or height <= 0.0:
        return
    program, quad = _flame_pipeline()
    left, right, bottom, top = _camera_view()
    dx, dy = DIRECTION_VECTOR[_normalize_direction(direction)]
    program["u_origin"] = origin_x, origin_y
    program["u_size"] = length, height
    program["u_dir"] = dx, dy
    program["u_view"] = left, right, bottom, top
    program["u_time"] = time_value
    program["u_intensity"] = intensity
    program["u_seed"] = seed
    program["u_aspect"] = length / height
    program["u_pad"] = settings.FLAMETHROWER_VISUAL_PAD
    with additive_blend():
        quad.render(program)


def _flame_pipeline():
    global _PROGRAM, _QUAD
    if _PROGRAM is None or _QUAD is None:
        ctx = arcade.get_window().ctx
        _PROGRAM = ctx.program(vertex_shader=_VERTEX_SHADER, fragment_shader=_FRAGMENT_SHADER)
        _QUAD = geometry.quad_2d()
    return _PROGRAM, _QUAD


def _camera_view() -> tuple[float, float, float, float]:
    window = arcade.get_window()
    camera = getattr(window, "current_camera", None)
    position = getattr(camera, "position", None)
    width = getattr(camera, "width", None)
    height = getattr(camera, "height", None)
    if position is None or width is None or height is None:
        return 0.0, float(window.width), 0.0, float(window.height)
    center_x = float(position[0])
    center_y = float(position[1])
    half_w = float(width) / 2
    half_h = float(height) / 2
    return center_x - half_w, center_x + half_w, center_y - half_h, center_y + half_h
