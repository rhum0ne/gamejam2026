"""Plaques d'activation et blocs qu'elles commandent.

Une plaque reagit a un poids (corps, cadavre, ennemi) : tant qu'elle est
enfoncee, les tuiles `setBlock type=void` disparaissent. Des qu'elle est
relachee, les blocs reviennent, sauf s'ils recouvriraient encore un corps.

Le fantome ne pese pas. Les liens plaque -> cibles se dessinent dans
`PlayView`, uniquement en mode fantome.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import arcade

import settings
from src.entities.glow import additive_blend, draw_glow
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


@dataclass(slots=True)
class Mechanism:
    """Une plaque et les blocs qu'elle commande."""

    plate: PressurePlate
    targets: list[GatedTile] = field(default_factory=list)
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
        """Aura silhouette + vrilles d'ame, uniquement en mode fantome."""
        with additive_blend():
            draw_sprite_soul_aura(self.plate, now, seed=0)
            for index, tile in enumerate(self.targets):
                draw_sprite_soul_aura(tile.sprite, now, seed=index + 1)
            start = (self.plate.center_x, self.plate.center_y)
            total = len(self.targets)
            for index, tile in enumerate(self.targets):
                draw_organic_link(
                    start,
                    (tile.sprite.center_x, tile.sprite.center_y),
                    strand=index,
                    strand_count=total,
                    now=now,
                )


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
) -> None:
    """Trainee d'ame floue le long d'une vrille, plus quelques motes qui derivent."""
    points = _organic_link_points(start, end, strand, strand_count, now)
    if len(points) < 2:
        return
    color = settings.COLOR_MECHANISM_LINK
    blur_size = settings.MECHANISM_LINK_STAMP_SIZE * settings.MECHANISM_LINK_BLUR_SCALE
    for x, y in _even_points(points, settings.MECHANISM_LINK_STAMP_SPACING * 1.5):
        draw_glow(
            x,
            y,
            blur_size,
            blur_size,
            color,
            settings.MECHANISM_LINK_BLUR_ALPHA,
            bind_blend=False,
        )
    for x, y in _even_points(points, settings.MECHANISM_LINK_STAMP_SPACING):
        draw_glow(
            x,
            y,
            settings.MECHANISM_LINK_STAMP_SIZE,
            settings.MECHANISM_LINK_STAMP_SIZE,
            color,
            settings.MECHANISM_LINK_STAMP_ALPHA,
            bind_blend=False,
        )
    last = len(points) - 1
    mote_count = settings.MECHANISM_LINK_MOTE_COUNT
    for mote in range(mote_count):
        travel = (now * settings.MECHANISM_LINK_MOTE_SPEED + (mote + strand * 0.17) / mote_count) % 1.0
        index = max(0, min(last, int(travel * last)))
        x, y = points[index]
        pulse = 0.55 + 0.45 * math.sin(now * 3.1 + mote + strand)
        size = settings.MECHANISM_LINK_MOTE_SIZE * pulse
        draw_glow(
            x,
            y,
            size,
            size,
            color,
            int(settings.MECHANISM_LINK_MOTE_ALPHA * pulse),
            bind_blend=False,
        )


def draw_sprite_soul_aura(sprite: arcade.Sprite, now: float, *, seed: int) -> None:
    """Detourage lumineux de `sprite` : voile flou + motes le long du contour.

    Arcade `Sprite.top/bottom/left/right` suivent la *hitbox*. La plaque a une
    hitbox d'une tuile pour le poids, mais sa lamelle visuelle n'a que
    `PLATE_HEIGHT` : on detoure donc `width`/`height` autour du centre.
    """
    width = abs(sprite.width)
    height = abs(sprite.height)
    if width < 1.0 or height < 1.0:
        return
    color = settings.COLOR_MECHANISM_GLOW
    pulse = 1.0 + settings.MECHANISM_AURA_PULSE * math.sin(
        now * settings.MECHANISM_LINK_PULSE_SPEED + seed
    )
    pad_x = _axis_pad(width)
    pad_y = _axis_pad(height)
    fill_alpha = int(settings.MECHANISM_AURA_FILL_ALPHA * pulse)
    edge_alpha = int(settings.MECHANISM_AURA_EDGE_ALPHA * pulse)
    left, right, bottom, top = _visual_bounds(sprite)
    center_x = (left + right) / 2.0
    center_y = (bottom + top) / 2.0
    outer = settings.MECHANISM_AURA_OUTER_SCALE
    draw_glow(
        center_x,
        center_y,
        width + pad_x * outer,
        height + pad_y,
        color,
        max(1, fill_alpha // 2),
        bind_blend=False,
    )
    draw_glow(
        center_x,
        center_y,
        width + pad_x * 0.35,
        height + pad_y * 0.35,
        color,
        fill_alpha,
        bind_blend=False,
    )
    draw_glow(
        center_x,
        top,
        width + pad_x,
        pad_y,
        color,
        edge_alpha,
        bind_blend=False,
    )
    draw_glow(
        center_x,
        bottom,
        width + pad_x,
        pad_y,
        color,
        edge_alpha,
        bind_blend=False,
    )
    draw_glow(
        left,
        center_y,
        pad_x,
        height,
        color,
        edge_alpha,
        bind_blend=False,
    )
    draw_glow(
        right,
        center_y,
        pad_x,
        height,
        color,
        edge_alpha,
        bind_blend=False,
    )
    _draw_silhouette_motes(left, right, bottom, top, now, seed, color, pulse, pad_x, pad_y)


def _visual_bounds(sprite: arcade.Sprite) -> tuple[float, float, float, float]:
    """Boite d'affichage (pas la hitbox) : left, right, bottom, top."""
    half_w = abs(sprite.width) / 2.0
    half_h = abs(sprite.height) / 2.0
    center_x = sprite.center_x
    center_y = sprite.center_y
    return (
        center_x - half_w,
        center_x + half_w,
        center_y - half_h,
        center_y + half_h,
    )


def _axis_pad(size: float) -> float:
    """Pad d'un axe, borne par la taille reelle du sprite (plaque plate vs bloc)."""
    return min(
        settings.MECHANISM_AURA_EDGE,
        max(settings.MECHANISM_AURA_MIN_PAD, size * settings.MECHANISM_AURA_AXIS_RATIO),
    )


def _draw_silhouette_motes(
    left: float,
    right: float,
    bottom: float,
    top: float,
    now: float,
    seed: int,
    color: tuple[int, int, int],
    pulse: float,
    pad_x: float,
    pad_y: float,
) -> None:
    width = max(1.0, right - left)
    height = max(1.0, top - bottom)
    perimeter = 2.0 * (width + height)
    count = max(4, int(perimeter / settings.MECHANISM_AURA_MOTE_SPACING))
    center_x = (left + right) / 2.0
    center_y = (bottom + top) / 2.0
    mote_size_cap = min(settings.MECHANISM_AURA_MOTE_SIZE, min(width, height) * 0.7 + 2.0)
    max_top = top + pad_y * 0.5
    min_bottom = bottom - pad_y * 0.5
    for index in range(count):
        t = (
            now * settings.MECHANISM_AURA_MOTE_SPEED
            + index / count
            + seed * 0.07
        ) % 1.0
        x, y = _perimeter_point(left, right, bottom, top, t)
        away_x = x - center_x
        away_y = y - center_y
        length = math.hypot(away_x, away_y) or 1.0
        drift = settings.MECHANISM_AURA_MOTE_DRIFT * (
            0.65 + 0.35 * math.sin(now * 2.4 + index + seed)
        )
        scale_x = min(1.0, pad_x / max(settings.MECHANISM_AURA_MIN_PAD, pad_y))
        scale_y = min(1.0, pad_y / max(settings.MECHANISM_AURA_MIN_PAD, pad_x))
        x += away_x / length * drift * scale_x
        y += away_y / length * drift * scale_y
        y = min(max_top, max(min_bottom, y))
        size = mote_size_cap * (
            0.55 + 0.45 * math.sin(now * 3.3 + index * 1.7)
        )
        draw_glow(
            x,
            y,
            size,
            size,
            color,
            int(settings.MECHANISM_AURA_MOTE_ALPHA * pulse),
            bind_blend=False,
        )


def _perimeter_point(
    left: float,
    right: float,
    bottom: float,
    top: float,
    t: float,
) -> tuple[float, float]:
    width = max(1.0, right - left)
    height = max(1.0, top - bottom)
    distance = (t % 1.0) * 2.0 * (width + height)
    if distance <= width:
        return left + distance, top
    distance -= width
    if distance <= height:
        return right, top - distance
    distance -= height
    if distance <= width:
        return right - distance, bottom
    distance -= width
    return left, bottom + distance


def _even_points(
    points: Sequence[tuple[float, float]],
    spacing: float,
) -> list[tuple[float, float]]:
    """Reechantillonne une polyligne a intervalle `spacing`."""
    if len(points) < 2 or spacing <= 0:
        return list(points)
    sampled: list[tuple[float, float]] = [points[0]]
    remaining = spacing
    previous = points[0]
    for current in points[1:]:
        dx = current[0] - previous[0]
        dy = current[1] - previous[1]
        dist = math.hypot(dx, dy)
        while dist >= remaining and dist > 0:
            ratio = remaining / dist
            previous = (previous[0] + dx * ratio, previous[1] + dy * ratio)
            sampled.append(previous)
            dx = current[0] - previous[0]
            dy = current[1] - previous[1]
            dist = math.hypot(dx, dy)
            remaining = spacing
        remaining -= dist
        previous = current
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


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
    # S : un controle d'un cote, l'autre de l'oppose, plus un eventail entre brins.
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
    segments = max(
        settings.MECHANISM_LINK_MIN_SEGMENTS,
        int(length / settings.MECHANISM_LINK_SPACING),
    )
    phase = now * settings.MECHANISM_LINK_PULSE_SPEED + bias * math.pi
    points: list[tuple[float, float]] = []
    for index in range(segments + 1):
        t = index / segments
        point_x, point_y = _cubic_bezier(start, control_a, control_b, end, t)
        envelope = math.sin(math.pi * t)
        wave = math.sin(
            2.0 * math.pi * settings.MECHANISM_LINK_WIGGLE_WAVES * t + phase
        )
        harmonic = math.sin(
            2.0 * math.pi * settings.MECHANISM_LINK_WIGGLE_WAVES * 2.15 * t
            + phase * 0.6
        )
        wiggle = settings.MECHANISM_LINK_WIGGLE * envelope * (wave + 0.32 * harmonic)
        points.append((point_x + perp_x * wiggle, point_y + perp_y * wiggle))
    return points


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
