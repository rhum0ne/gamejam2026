"""Ressorts : tuile orientable qui relance le corps physique.

Pas solides : ce sont des triggers. Un contact par la face active
- vertical : conserve l'elan horizontal et impose `SPRING_LAUNCH_SPEED` ;
- horizontal : inverse `change_x`.

L'orientation (4 axes) vit dans le champ JSON `springs`, comme les
lance-flammes. H dans l'editeur fait tourner la face active.
"""

from __future__ import annotations

from dataclasses import dataclass

import arcade
from PIL import Image, ImageDraw

import settings
from src.ui import sprites
from src.world.flamethrower import DIRECTION_CYCLE, DIRECTION_VECTOR, aim_sprite

_TEXTURE_CACHE: dict[int, arcade.Texture] = {}


def _normalize_direction(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("dir doit etre right, down, left ou up")
    key = value.strip().lower()
    if key not in DIRECTION_VECTOR:
        raise ValueError(f"dir inconnu : {value!r}")
    return key


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} doit etre un entier")
    return value


def spring_texture(size: int) -> arcade.Texture:
    """Bobine procedurale orientee vers la droite (pad a droite), mise en cache."""
    if size <= 0:
        raise ValueError("size doit etre strictement positif")
    cached = _TEXTURE_CACHE.get(size)
    if cached is not None:
        return cached
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    body = (*settings.COLOR_SPRING, 255)
    coil = (*settings.COLOR_SPRING_COIL, 255)
    pad = (*settings.COLOR_SPRING_PAD, 255)
    inset = max(1, size // 16)
    mid_y = size // 2
    coil_left = inset + size // 8
    coil_right = size - inset - size // 5
    draw.rectangle(
        (inset, mid_y - size // 5, coil_left + 1, mid_y + size // 5),
        fill=body,
        outline=coil,
    )
    steps = 6
    span = max(1, coil_right - coil_left)
    amp = max(3, size // 5)
    width = max(2, size // 12)
    points: list[tuple[int, int]] = []
    for index in range(steps + 1):
        x = coil_left + int(span * index / steps)
        y = mid_y + (amp if index % 2 else -amp)
        points.append((x, y))
    draw.line(points, fill=coil, width=width)
    pad_left = coil_right - 1
    draw.rectangle(
        (pad_left, inset + 1, size - inset - 1, size - inset - 2),
        fill=pad,
        outline=coil,
    )
    texture = arcade.Texture(image, hash=f"spring|{size}")
    _TEXTURE_CACHE[size] = texture
    return texture


@dataclass(frozen=True, slots=True)
class SpringSpec:
    """Orientation d'un ressort, en coordonnees de grille."""

    column: int
    row: int
    direction: str = "up"

    def __post_init__(self) -> None:
        if self.column < 0 or self.row < 0:
            raise ValueError("column et row doivent etre positifs")
        object.__setattr__(self, "direction", _normalize_direction(self.direction))

    def rotated(self) -> SpringSpec:
        index = DIRECTION_CYCLE.index(self.direction)
        nxt = DIRECTION_CYCLE[(index + 1) % len(DIRECTION_CYCLE)]
        return SpringSpec(self.column, self.row, nxt)

    def to_json(self) -> dict:
        return {"x": self.column, "y": self.row, "dir": self.direction}


class Spring(arcade.Sprite):
    """Pad trigger : relance le corps, traverse par le fantome."""

    ghost_passable = True
    slippery = False
    lethal_for_body = False

    def __init__(
        self,
        center_x: float,
        center_y: float,
        *,
        size: int = settings.TILE_SIZE,
        direction: str = "up",
    ) -> None:
        texture = spring_texture(size)
        super().__init__(
            texture,
            scale=sprites.scale_for_size(texture, size),
            center_x=center_x,
            center_y=center_y,
        )
        self.direction = _normalize_direction(direction)
        aim_sprite(self, self.direction)
        sprites.apply_rect_hit_box(self, size, size)
        self._size = size
        self._cooldown = 0.0

    @property
    def is_vertical(self) -> bool:
        return self.direction in ("up", "down")

    def tick(self, delta_time: float = settings.FRAME_TIME) -> None:
        if self._cooldown > 0.0:
            self._cooldown = max(0.0, self._cooldown - max(0.0, delta_time))

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        self.tick(delta_time)

    def can_launch(self, rider: arcade.Sprite) -> bool:
        """True si le contact vient de la face active (pas deja en train de rebondir)."""
        if self._cooldown > 0.0:
            return False
        dx, dy = DIRECTION_VECTOR[self.direction]
        along = rider.change_x * dx + rider.change_y * dy
        return along <= settings.SPRING_APPROACH

    def launch(self, rider: arcade.Sprite) -> None:
        """Applique l'impulsion, ecarte le corps, arme le cooldown."""
        dx, dy = DIRECTION_VECTOR[self.direction]
        if self.is_vertical:
            bounce = getattr(rider, "launch_vertical", None)
            if bounce is not None:
                bounce(dy * settings.SPRING_LAUNCH_SPEED)
            else:
                rider.change_y = dy * settings.SPRING_LAUNCH_SPEED
        else:
            bounce = getattr(rider, "reverse_horizontal", None)
            if bounce is not None:
                bounce(1 if dx >= 0 else -1)
            else:
                rider.change_x = -rider.change_x
        self._separate(rider)
        self._cooldown = settings.SPRING_COOLDOWN

    def _separate(self, rider: arcade.Sprite) -> None:
        pad = 1.0
        dx, dy = DIRECTION_VECTOR[self.direction]
        if abs(dx) >= abs(dy):
            if dx > 0.0:
                rider.left = self.right + pad
            else:
                rider.right = self.left - pad
            return
        if dy > 0.0:
            rider.bottom = self.top + pad
        else:
            rider.top = self.bottom - pad


def parse_spring_specs(raw: object) -> dict[tuple[int, int], SpringSpec]:
    """Lit le champ `springs` d'une carte, ou {} s'il est absent."""
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError("springs doit etre une liste")
    specs: dict[tuple[int, int], SpringSpec] = {}
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"springs[{index}] doit etre un objet")
        try:
            column = _as_int(entry.get("x"), "x")
            row = _as_int(entry.get("y"), "y")
            direction = entry.get("dir", "up")
            spec = SpringSpec(column, row, direction)
        except ValueError as error:
            raise ValueError(f"springs[{index}] : {error}") from error
        specs[(spec.column, spec.row)] = spec
    return specs


def dump_spring_specs(specs: dict[tuple[int, int], SpringSpec]) -> list[dict]:
    """Serialise les ressorts, tries par position."""
    return [specs[key].to_json() for key in sorted(specs)]
