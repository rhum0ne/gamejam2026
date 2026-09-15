"""Panneau de debug en jeu (FPS, etats, tuiles visibles, camera).

Active par `settings.DEBUG_OVERLAY`, basculable avec F3 pendant une partie.
"""

from __future__ import annotations

from dataclasses import dataclass

import arcade

import settings
from src.ui.fonts import PIXEL_FONT

_LINE_COUNT = 12
_LINE_HEIGHT = 16
_PADDING = 10


@dataclass(slots=True)
class DebugSnapshot:
    """Instantane des infos de debug pour une frame."""

    fps: float = 0.0
    state: str = ""
    player_x: float = 0.0
    player_y: float = 0.0
    player_vx: float = 0.0
    player_vy: float = 0.0
    on_ground: bool = False
    alive: bool = False
    ghost_x: float | None = None
    ghost_y: float | None = None
    ghost_time: float | None = None
    leash_ratio: float = 0.0
    camera_x: float = 0.0
    camera_y: float = 0.0
    view_w: float = 0.0
    view_h: float = 0.0
    window_w: int = 0
    window_h: int = 0
    fullscreen: bool = False
    tiles_visible: int = 0
    tiles_total: int = 0
    walls_visible: int = 0
    walls_total: int = 0
    enemies: int = 0
    items: int = 0
    corpses: int = 0
    enemy_states: str = ""
    deaths: int = 0
    essence: int = 0
    extra: tuple[str, ...] = ()


class DebugOverlay:
    """Bloc de texte ancre en bas a gauche, au-dessus de la camera UI."""

    def __init__(self) -> None:
        self._lines = [
            arcade.Text(
                "",
                _PADDING + 6,
                _PADDING + 6 + index * _LINE_HEIGHT,
                settings.COLOR_DEBUG,
                font_size=11,
                font_name=PIXEL_FONT,
            )
            for index in range(_LINE_COUNT)
        ]

    def draw(self, data: DebugSnapshot) -> None:
        """Dessine le fond puis les lignes de `data`."""
        rows = self._format(data)
        width = 8 + max((len(row) for row in rows), default=1) * 7
        height = _PADDING * 2 + len(rows) * _LINE_HEIGHT
        arcade.draw_lrbt_rectangle_filled(
            4, 4 + width, 4, 4 + height, settings.COLOR_DEBUG_PANEL
        )
        for index, line in enumerate(self._lines):
            if index >= len(rows):
                break
            line.text = rows[index]
            line.y = _PADDING + 8 + (len(rows) - 1 - index) * _LINE_HEIGHT
            line.draw()

    def _format(self, data: DebugSnapshot) -> list[str]:
        ghost = "off"
        if data.ghost_x is not None and data.ghost_y is not None:
            time_left = data.ghost_time if data.ghost_time is not None else 0.0
            ghost = (
                f"{data.ghost_x:.0f},{data.ghost_y:.0f}  "
                f"t={time_left:.1f}s  leash={data.leash_ratio:.0%}"
            )
        ground = "ground" if data.on_ground else "air"
        life = "alive" if data.alive else "dead"
        screen = "FS" if data.fullscreen else "win"
        rows = [
            f"FPS {data.fps:5.1f}   {data.state}   deaths={data.deaths}  essence={data.essence}",
            f"player {data.player_x:7.1f},{data.player_y:7.1f}  "
            f"v={data.player_vx:+5.1f},{data.player_vy:+5.1f}  {ground} {life}",
            f"ghost  {ghost}",
            f"camera {data.camera_x:.0f},{data.camera_y:.0f}  "
            f"view {data.view_w:.0f}x{data.view_h:.0f}  "
            f"{screen} {data.window_w}x{data.window_h}",
            f"tiles  {data.tiles_visible}/{data.tiles_total} drawn  "
            f"(walls {data.walls_visible}/{data.walls_total})",
            f"ents   enemies={data.enemies}  items={data.items}  corpses={data.corpses}"
            + (f"  ia={data.enemy_states}" if data.enemy_states else ""),
            "F3 toggle overlay",
        ]
        rows.extend(data.extra)
        return rows[:_LINE_COUNT]
