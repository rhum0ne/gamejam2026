"""Overlay pause : le niveau reste charge, le jeu est gele."""

from __future__ import annotations

from collections.abc import Callable

import arcade

import settings
from src.ui.display import handle_display_key, toggle_fullscreen
from src.ui.fonts import PIXEL_FONT
from src.ui.menu_kit import ButtonColumn, TextButton, draw_panel
from src.ui.pad import get_pad


class PauseMenu:
    """Voile + panneau. Les callbacks viennent de `PlayView`."""

    def __init__(
        self,
        *,
        on_resume: Callable[[], None],
        on_retry: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.on_resume = on_resume
        self.on_retry = on_retry
        self.on_quit = on_quit
        self.title = arcade.Text(
            "PAUSE",
            0,
            0,
            settings.COLOR_MENU_TITLE,
            font_size=18,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        self.hint = arcade.Text(
            "Echap pour reprendre",
            0,
            0,
            settings.COLOR_MENU_HINT,
            font_size=10,
            anchor_x="center",
            font_name=PIXEL_FONT,
        )
        self.column = ButtonColumn()
        self._layout_w = 0.0
        self._layout_h = 0.0
        self._panel = (0.0, 0.0, 0.0, 0.0)

    def layout(self, width: float, height: float) -> None:
        if width == self._layout_w and height == self._layout_h and self.column.buttons:
            return
        self._layout_w = width
        self._layout_h = height
        panel_w = 380.0
        panel_h = 320.0
        cx, cy = width / 2, height / 2
        left, right = cx - panel_w / 2, cx + panel_w / 2
        bottom, top = cy - panel_h / 2, cy + panel_h / 2
        self._panel = (left, right, bottom, top)
        self.title.x = cx
        self.title.y = top - 40
        self.hint.x = cx
        self.hint.y = bottom + 28
        self.column.set_buttons(
            (
                TextButton("Reprendre", on_activate=self.on_resume),
                TextButton("Recommencer", on_activate=self.on_retry),
                TextButton("Plein ecran", on_activate=self._toggle_fullscreen),
                TextButton("Menu principal", on_activate=self.on_quit),
            )
        )
        self.column.layout(cx, self.title.y - 56)

    def _toggle_fullscreen(self) -> None:
        toggle_fullscreen(arcade.get_window())

    def draw(self, width: float, height: float) -> None:
        self.layout(width, height)
        arcade.draw_lrbt_rectangle_filled(
            0,
            width,
            0,
            height,
            (*settings.COLOR_MENU_VEIL, settings.MENU_PAUSE_VEIL_ALPHA),
        )
        left, right, bottom, top = self._panel
        draw_panel(left, right, bottom, top, accent=settings.COLOR_MENU_FOCUS)
        self.title.draw()
        self.column.draw()
        self.hint.text = (
            "+ pour reprendre" if get_pad().using_pad else "Echap pour reprendre"
        )
        self.hint.draw()

    def on_key_press(self, window: arcade.Window, symbol: int, modifiers: int) -> None:
        if handle_display_key(window, symbol, modifiers):
            return
        if symbol == arcade.key.ESCAPE:
            self.on_resume()
            return
        self.column.on_key_press(symbol)

    def on_mouse_motion(self, x: float, y: float) -> None:
        self.column.on_mouse_motion(x, y)

    def on_mouse_press(self, x: float, y: float) -> None:
        self.column.on_mouse_press(x, y)

    def on_mouse_release(self, x: float, y: float) -> None:
        self.column.on_mouse_release(x, y)
