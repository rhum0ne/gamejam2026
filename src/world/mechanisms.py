"""Plaques d'activation et blocs qu'elles commandent.

Une plaque reagit a un poids (corps, cadavre, ennemi) : tant qu'elle est
enfoncee, les tuiles `setBlock type=void` disparaissent. Des qu'elle est
relachee, les blocs reviennent, sauf s'ils recouvriraient encore un corps.

Le fantome ne pese pas. Les liens plaque -> paquets de blocs se dessinent
dans `PlayView`, uniquement en mode fantome : un brin par groupe connexe,
pas une ligne par tuile.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import arcade

import settings
from src.entities.glow import draw_glow
from src.ui import sprites


class PressurePlate(arcade.SpriteSolidColor):
    """Capteur au sol, non solide : on marche dessus sans etre bloque."""

    def __init__(
        self,
        center_x: float,
        center_y: float,
        width: float,
        height: float = settings.PLATE_HEIGHT,
    ) -> None:
        super().__init__(
            int(width),
            int(height),
            center_x=center_x,
            center_y=center_y,
            color=settings.COLOR_PRESSURE_PLATE,
        )
        self.pressed = False
        # Hitbox = la tuile entiere, pas la lamelle visuelle : un cadavre nait
        # au centre du joueur, au-dessus de la plaque, et doit quand meme compter.
        hit_height = settings.TILE_SIZE
        sprites.apply_rect_hit_box(
            self,
            width,
            hit_height,
            offset_y=hit_height / 2 - height / 2,
        )

    def set_pressed(self, pressed: bool) -> None:
        if pressed == self.pressed:
            return
        self.pressed = pressed
        self.color = (
            settings.COLOR_PRESSURE_PLATE_PRESSED
            if pressed
            else settings.COLOR_PRESSURE_PLATE
        )


@dataclass(slots=True)
class GatedTile:
    """Bloc de terrain que la plaque peut retirer puis remettre."""

    sprite: arcade.Sprite
    lists: tuple[arcade.SpriteList, ...]
    hidden: bool = False

    def hide(self) -> None:
        if self.hidden:
            return
        self.sprite.remove_from_sprite_lists()
        self.hidden = True

    def show(self) -> None:
        if not self.hidden:
            return
        for sprite_list in self.lists:
            sprite_list.append(self.sprite)
        self.hidden = False

    def overlaps_any(self, sprites: Sequence[arcade.Sprite]) -> bool:
        return any(arcade.check_for_collision(self.sprite, other) for other in sprites)


@dataclass(frozen=True, slots=True)
class GatedChunk:
    """Groupe connexe de tuiles commandees : un seul lien vers son centre."""

    tiles: tuple[GatedTile, ...]
    center_x: float
    center_y: float
    width: float
    height: float


@dataclass(slots=True)
class Mechanism:
    """Une plaque et les blocs qu'elle commande."""

    plate: PressurePlate
    targets: list[GatedTile] = field(default_factory=list)
    chunks: tuple[GatedChunk, ...] = ()
    pressed: bool = False

    def set_pressed(self, pressed: bool, occupants: Sequence[arcade.Sprite]) -> None:
        """Applique l'etat de la plaque : retire ou restitue les cibles."""
        self.pressed = pressed
        self.plate.set_pressed(pressed)
        if pressed:
            for tile in self.targets:
                tile.hide()
            return
        for tile in self.targets:
            if tile.overlaps_any(occupants):
                continue
            tile.show()

    def draw_soul(self, now: float) -> None:
        """Plaque lumineuse, vrille fantome, paquets discrets."""
        active = 1.0 + (settings.MECHANISM_PRESSED_GLOW - 1.0) * float(self.pressed)
        draw_plate_glow(self.plate, now, intensity=active)
        start = (self.plate.center_x, self.plate.center_y)
        chunks = self.chunks or group_gated_chunks(self.targets, settings.TILE_SIZE)
        total = max(1, len(chunks))
        for index, chunk in enumerate(chunks):
            draw_chunk_soul_aura(chunk, now, seed=index + 1, intensity=active)
            draw_organic_link(
                start,
                (chunk.center_x, chunk.center_y),
                strand=index,
                strand_count=total,
                now=now,
                intensity=active,
            )


def group_gated_chunks(
    tiles: Sequence[GatedTile],
    tile_size: float,
) -> tuple[GatedChunk, ...]:
    """Regroupe les tuiles 4-connexes : un paquet = un lien, pas 10000 lignes."""
    remaining = list(tiles)
    chunks: list[GatedChunk] = []
    while remaining:
        seed = remaining.pop()
        cluster = [seed]
        stack = [seed]
        while stack:
            current = stack.pop()
            still: list[GatedTile] = []
            for other in remaining:
                if _tiles_adjacent(current, other, tile_size):
                    cluster.append(other)
                    stack.append(other)
                else:
                    still.append(other)
            remaining = still
        chunks.append(_chunk_from_tiles(cluster))
    return tuple(chunks)


def plate_geometry(
    column: int,
    row: int,
    width_tiles: int,
    tile_size: int,
    total_rows: int,
) -> tuple[float, float, float, float]:
    """Retourne (center_x, center_y, width, height) d'une plaque en coordonnees monde."""
    width = width_tiles * tile_size - 2 * settings.PLATE_INSET
    height = settings.PLATE_HEIGHT
    origin_x = column * tile_size
    origin_y = (total_rows - 1 - row) * tile_size
    center_x = origin_x + (width_tiles * tile_size) / 2
    center_y = origin_y + height / 2
    return center_x, center_y, width, height


def draw_organic_link(
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    strand: int,
    strand_count: int,
    now: float,
    intensity: float = 1.0,
) -> None:
    """Brume organique : une nappe de halos, sans trait net."""
    points = _organic_link_points(start, end, strand, strand_count, now)
    if len(points) < 2:
        return
    mist = settings.COLOR_MECHANISM_LINK
    core = settings.COLOR_MECHANISM_GLOW_CORE
    mist_alpha = max(1, min(255, int(settings.MECHANISM_LINK_GLOW_ALPHA * intensity)))
    core_alpha = max(1, min(255, int(settings.MECHANISM_LINK_CORE_ALPHA * intensity)))
    mist_size = settings.MECHANISM_LINK_GLOW_SIZE
    core_size = settings.MECHANISM_LINK_CORE_SIZE
    for point_x, point_y in points:
        draw_glow(point_x, point_y, mist_size, mist_size * 0.78, mist, mist_alpha)
        draw_glow(point_x, point_y, core_size, core_size * 0.78, core, core_alpha)
    flow_alpha = max(1, min(255, int(settings.MECHANISM_LINK_FLOW_ALPHA * intensity)))
    flow_core_alpha = max(
        1, min(255, int(settings.MECHANISM_LINK_FLOW_CORE_ALPHA * intensity))
    )
    flow_size = settings.MECHANISM_LINK_FLOW_SIZE
    flow_core = settings.MECHANISM_LINK_FLOW_CORE_SIZE
    count = max(1, settings.MECHANISM_LINK_FLOW_COUNT)
    phase = now * settings.MECHANISM_LINK_FLOW_SPEED + strand * 0.37
    for index in range(count):
        t = (phase + index / count) % 1.0
        point_x, point_y = _point_along(points, t)
        draw_glow(point_x, point_y, flow_size, flow_size * 0.8, mist, flow_alpha)
        draw_glow(point_x, point_y, flow_core, flow_core * 0.8, core, flow_core_alpha)


def draw_plate_glow(
    plate: arcade.Sprite,
    now: float,
    *,
    intensity: float = 1.0,
) -> None:
    """Nappe floue autour de la plaque : large, douce, sans bord net."""
    pulse = 1.0 + settings.MECHANISM_AURA_PULSE * math.sin(
        now * settings.MECHANISM_LINK_PULSE_SPEED
    )
    breathe = 1.0 + 0.08 * math.sin(now * settings.MECHANISM_LINK_PULSE_SPEED * 0.55)
    strength = pulse * intensity
    center_x = plate.center_x
    center_y = plate.center_y
    outer = settings.MECHANISM_PLATE_GLOW_SIZE * breathe
    mid = settings.MECHANISM_PLATE_GLOW_MID * breathe
    inner = settings.MECHANISM_PLATE_GLOW_INNER
    draw_glow(
        center_x,
        center_y,
        outer,
        outer * 0.7,
        settings.COLOR_MECHANISM_GLOW,
        max(1, min(255, int(settings.MECHANISM_PLATE_GLOW_ALPHA * strength))),
    )
    draw_glow(
        center_x,
        center_y,
        mid,
        mid * 0.72,
        settings.COLOR_MECHANISM_GLOW,
        max(1, min(255, int(settings.MECHANISM_PLATE_GLOW_MID_ALPHA * strength))),
    )
    draw_glow(
        center_x,
        center_y,
        inner,
        inner * 0.75,
        settings.COLOR_MECHANISM_GLOW_CORE,
        max(1, min(255, int(settings.MECHANISM_PLATE_GLOW_INNER_ALPHA * strength))),
    )


def draw_chunk_soul_aura(
    chunk: GatedChunk,
    now: float,
    *,
    seed: int,
    intensity: float = 1.0,
) -> None:
    """Un halo pour tout le paquet, meme si les tuiles sont deja cachees."""
    _draw_box_aura(
        chunk.center_x,
        chunk.center_y,
        chunk.width,
        chunk.height,
        now,
        seed=seed,
        intensity=intensity,
    )


def _draw_box_aura(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    now: float,
    *,
    seed: int,
    intensity: float,
) -> None:
    if width < 1.0 or height < 1.0:
        return
    pulse = 1.0 + settings.MECHANISM_AURA_PULSE * math.sin(
        now * settings.MECHANISM_LINK_PULSE_SPEED + seed
    )
    strength = pulse * intensity
    pad_x = _axis_pad(width)
    pad_y = _axis_pad(height)
    outer = settings.MECHANISM_AURA_OUTER_SCALE
    draw_glow(
        center_x,
        center_y,
        width + pad_x * outer,
        height + pad_y * outer,
        settings.COLOR_MECHANISM_GLOW,
        max(1, min(255, int(settings.MECHANISM_AURA_FILL_ALPHA * strength))),
    )
    draw_glow(
        center_x,
        center_y,
        width + pad_x * 0.45,
        height + pad_y * 0.45,
        settings.COLOR_MECHANISM_GLOW_CORE,
        max(1, min(255, int(settings.MECHANISM_AURA_CORE_ALPHA * strength))),
    )


def _tiles_adjacent(left: GatedTile, right: GatedTile, tile_size: float) -> bool:
    """Voisins ortho (4-connexes), avec un slop d'un pixel sur le centrage."""
    delta_x = abs(left.sprite.center_x - right.sprite.center_x)
    delta_y = abs(left.sprite.center_y - right.sprite.center_y)
    slop = 1.0
    same_row = delta_y <= slop and delta_x <= tile_size + slop
    same_col = delta_x <= slop and delta_y <= tile_size + slop
    return same_row or same_col


def _chunk_from_tiles(tiles: Sequence[GatedTile]) -> GatedChunk:
    left = min(tile.sprite.center_x - abs(tile.sprite.width) / 2.0 for tile in tiles)
    right = max(tile.sprite.center_x + abs(tile.sprite.width) / 2.0 for tile in tiles)
    bottom = min(tile.sprite.center_y - abs(tile.sprite.height) / 2.0 for tile in tiles)
    top = max(tile.sprite.center_y + abs(tile.sprite.height) / 2.0 for tile in tiles)
    return GatedChunk(
        tiles=tuple(tiles),
        center_x=(left + right) / 2.0,
        center_y=(bottom + top) / 2.0,
        width=max(1.0, right - left),
        height=max(1.0, top - bottom),
    )


def _organic_link_points(
    start: tuple[float, float],
    end: tuple[float, float],
    strand: int,
    strand_count: int,
    now: float,
) -> list[tuple[float, float]]:
    x0, y0 = start
    x1, y1 = end
    delta_x = x1 - x0
    delta_y = y1 - y0
    length = math.hypot(delta_x, delta_y)
    if length < 1.0:
        return [start, end]
    dir_x = delta_x / length
    dir_y = delta_y / length
    perp_x = -dir_y
    perp_y = dir_x
    bias = _strand_bias(x0, y0, x1, y1, strand)
    fan = 0.0
    if strand_count > 1:
        fan = (strand - (strand_count - 1) / 2) / (strand_count - 1)
    bulge = length * settings.MECHANISM_LINK_CURVE
    side = 1.0 if bias >= 0 else -1.0
    offset_a = side * bulge + fan * settings.MECHANISM_LINK_FAN
    offset_b = -side * bulge * 0.72 + fan * settings.MECHANISM_LINK_FAN * 0.35
    control_a = (
        x0 + dir_x * length * 0.28 + perp_x * offset_a,
        y0 + dir_y * length * 0.28 + perp_y * offset_a,
    )
    control_b = (
        x0 + dir_x * length * 0.72 + perp_x * offset_b,
        y0 + dir_y * length * 0.72 + perp_y * offset_b,
    )
    segments = min(
        settings.MECHANISM_LINK_MAX_SEGMENTS,
        max(
            settings.MECHANISM_LINK_MIN_SEGMENTS,
            int(length / settings.MECHANISM_LINK_SPACING),
        ),
    )
    phase = now * settings.MECHANISM_LINK_PULSE_SPEED + bias * math.pi
    slow_phase = now * settings.MECHANISM_LINK_PULSE_SPEED * 0.37 + bias
    points: list[tuple[float, float]] = []
    for index in range(segments + 1):
        t = index / segments
        point_x, point_y = _cubic_bezier(start, control_a, control_b, end, t)
        envelope = math.sin(math.pi * t)
        wave = math.sin(
            2.0 * math.pi * settings.MECHANISM_LINK_WIGGLE_WAVES * t + phase
        )
        slow = math.sin(
            2.0 * math.pi * settings.MECHANISM_LINK_WIGGLE_SLOW_WAVES * t + slow_phase
        )
        wiggle = envelope * (
            settings.MECHANISM_LINK_WIGGLE * wave
            + settings.MECHANISM_LINK_WIGGLE_SLOW * slow
        )
        points.append((point_x + perp_x * wiggle, point_y + perp_y * wiggle))
    return points


def _point_along(
    points: Sequence[tuple[float, float]],
    t: float,
) -> tuple[float, float]:
    """Point a la fraction `t` (0..1) le long d'une polyligne."""
    if len(points) == 1:
        return points[0]
    total = 0.0
    lengths = [0.0]
    for index in range(1, len(points)):
        total += math.hypot(
            points[index][0] - points[index - 1][0],
            points[index][1] - points[index - 1][1],
        )
        lengths.append(total)
    if total < 1.0:
        return points[0]
    target = max(0.0, min(1.0, t)) * total
    for index in range(1, len(points)):
        if lengths[index] < target:
            continue
        span = lengths[index] - lengths[index - 1]
        ratio = 0.0 if span < 0.001 else (target - lengths[index - 1]) / span
        x0, y0 = points[index - 1]
        x1, y1 = points[index]
        return (x0 + (x1 - x0) * ratio, y0 + (y1 - y0) * ratio)
    return points[-1]


def _cubic_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    b0 = u * u * u
    b1 = 3.0 * u * u * t
    b2 = 3.0 * u * t * t
    b3 = t * t * t
    return (
        b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0],
        b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1],
    )


def _strand_bias(x0: float, y0: float, x1: float, y1: float, strand: int) -> float:
    """Valeur stable dans [-1, 1] pour qu'un brin ne change pas a chaque frame."""
    mixed = (
        int(x0) * 73856093
        ^ int(y0) * 19349663
        ^ int(x1) * 83492791
        ^ int(y1) * 50331653
        ^ strand * 2654435761
    )
    mixed &= 0xFFFFFFFF
    mixed ^= mixed >> 16
    mixed = (mixed * 0x7FEB352D) & 0xFFFFFFFF
    mixed ^= mixed >> 15
    return (mixed & 0xFFFF) / 32767.5 - 1.0


def _axis_pad(size: float) -> float:
    """Pad d'un axe, borne par la taille reelle du sprite (plaque plate vs bloc)."""
    return min(
        settings.MECHANISM_AURA_EDGE,
        max(settings.MECHANISM_AURA_MIN_PAD, size * settings.MECHANISM_AURA_AXIS_RATIO),
    )
