"""HUD en jeu : stats en icones, timer du fantome, invites clavier.

Le HUD est "sans etat" : la vue de jeu construit un `HudData` a chaque frame et
le passe a `Hud.draw()`. Les objets `arcade.Text` sont crees une seule fois
(leur creation est couteuse) puis mis a jour via leur attribut `.text`.

Coin haut-droit : une ligne par item (`icone  valeur`), jauge du fantome
sous le bloc. Plus de jauge de dash.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import arcade
from arcade.color import WHITE
from arcade.types import Color, XYWH

import settings
from src.ui import keys, sprites
from src.ui.fonts import PIXEL_FONT


@dataclass(frozen=True, slots=True)
class HudData:
    """Instantane des informations a afficher."""

    level_name: str
    state_label: str
    essence: int
    ghost_level: int
    hint: str = ""
    has_key: bool = False
    corpse_count: int = 0
    ghost_time_left: float | None = None
    ghost_duration: float = settings.GHOST_DURATION
    leash_ratio: float = 0.0
    fps: float | None = None
    controls: str = ""
    pressed_keys: frozenset[int] = frozenset()
    show_esprit: bool = False


class Hud:
    """Affichage des informations de jeu par-dessus la scene."""

    _MARGIN = 16

    def __init__(self, screen_width: int, screen_height: int) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        icon = settings.HUD_STAT_ICON
        self._soul_icon = sprites.soul_orb_texture(icon)
        self._key_icon = sprites.load_texture(settings.SPRITE_KEY, size=icon)
        self._key_empty = Color.from_iterable(settings.COLOR_HUD_KEY_EMPTY)
        self._build_texts()

    def _build_texts(self) -> None:
        screen_width, screen_height = self.screen_width, self.screen_height
        self._level_text = self._make_text("", self._MARGIN, screen_height - 30)
        self._state_text = self._make_text("", self._MARGIN, screen_height - 54, size=13)
        self._soul_value = self._make_stat_value()
        self._ghost_value = self._make_stat_value()
        self._key_value = self._make_stat_value()
        self._hint_text = self._make_text(
            "", screen_width / 2, self._MARGIN + 6, size=13, anchor_x="center"
        )
        self._fps_text = self._make_text(
            "", self._MARGIN, self._MARGIN + 6, size=12, color=settings.COLOR_MENU_HINT
        )

    def _make_stat_value(self) -> arcade.Text:
        return arcade.Text(
            "",
            0,
            0,
            settings.COLOR_HUD_TEXT,
            font_size=16,
            anchor_x="right",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )

    def _make_text(
        self,
        content: str,
        x: float,
        y: float,
        size: float = 16,
        anchor_x: str = "left",
        color: tuple[int, int, int] = settings.COLOR_HUD_TEXT,
    ) -> arcade.Text:
        return arcade.Text(
            content,
            x,
            y,
            color,
            font_size=size,
            anchor_x=anchor_x,
            font_name=PIXEL_FONT,
        )

    def draw(self, data: HudData, fade: float = 1.0) -> None:
        """Dessine le HUD a partir de l'instantane fourni."""
        fade = max(0.0, min(1.0, fade))
        if fade <= 0.02:
            return
        alpha = int(255 * fade)
        self._level_text.text = data.level_name
        self._state_text.text = data.state_label
        self._hint_text.text = data.hint
        self._level_text.color = (*settings.COLOR_HUD_TEXT, alpha)
        self._state_text.color = (*settings.COLOR_HUD_TEXT, alpha)
        self._hint_text.color = (*settings.COLOR_HUD_TEXT, alpha)

        self._level_text.draw()
        self._state_text.draw()
        self._draw_top_right(data, alpha)
        if data.fps is not None:
            self._fps_text.text = f"{data.fps:.0f} FPS"
            self._fps_text.color = (*settings.COLOR_MENU_HINT, alpha)
            self._fps_text.draw()
        if fade > 0.45:
            if data.controls == "playing":
                keys.draw_prompt_row(
                    self.screen_width / 2,
                    self._MARGIN + settings.UI_KEY_ICON_HEIGHT / 2 + 4,
                    keys.playing_prompts(show_esprit=data.show_esprit),
                    data.pressed_keys,
                )
            elif data.controls == "ghost":
                keys.draw_prompt_row(
                    self.screen_width / 2,
                    self._MARGIN + settings.UI_KEY_ICON_HEIGHT / 2 + 4,
                    keys.GHOST_PROMPTS,
                    data.pressed_keys,
                )
            elif data.hint:
                self._hint_text.text = data.hint
                self._hint_text.draw()

    def _draw_top_right(self, data: HudData, alpha: int) -> None:
        """Bloc vertical : une ligne par stat, jauge fantome en dessous."""
        right = float(self.screen_width - self._MARGIN)
        icon = settings.HUD_STAT_ICON
        row = icon + settings.HUD_STAT_GAP
        ghost_fill = (*settings.COLOR_HUD_GHOST_GAUGE, alpha)
        self._soul_value.text = str(data.essence)
        self._ghost_value.text = str(data.ghost_level)
        self._key_value.text = str(int(data.has_key))
        value_width = max(
            self._soul_value.content_width,
            self._ghost_value.content_width,
            self._key_value.content_width,
        )
        icon_x = right - value_width - settings.HUD_STAT_VALUE_GAP - icon / 2
        rows: tuple[tuple[arcade.Text, Callable[[float], None]], ...] = (
            (self._soul_value, lambda cy: self._draw_soul_icon(icon_x, cy, alpha)),
            (self._ghost_value, lambda cy: self._draw_ghost_icon(icon_x, cy, ghost_fill)),
            (
                self._key_value,
                lambda cy: self._draw_key_icon(icon_x, cy, data.has_key, alpha),
            ),
        )
        y = self.screen_height - self._MARGIN - icon / 2
        for label, draw_icon in rows:
            label.x = right
            label.y = y
            label.color = (*settings.COLOR_HUD_TEXT, alpha)
            label.draw()
            draw_icon(y)
            y -= row
        if data.ghost_time_left is None:
            return
        duration = max(data.ghost_duration, 0.001)
        ratio = max(0.0, min(1.0, data.ghost_time_left / duration))
        flash = 0.0
        if ratio <= settings.HUD_GAUGE_LOW:
            flash = 0.45 + 0.55 * abs((data.ghost_time_left * 6.0) % 1.0 - 0.5) * 2.0
        self._draw_ghost_gauge(right, y, ratio, flash, alpha)

    def _draw_soul_icon(self, center_x: float, center_y: float, alpha: int) -> None:
        size = settings.HUD_STAT_ICON
        arcade.draw_texture_rect(
            self._soul_icon,
            XYWH(center_x, center_y, size, size),
            pixelated=True,
            color=Color.from_iterable(settings.COLOR_SOUL_ORB),
            alpha=alpha,
        )

    def _draw_key_icon(
        self, center_x: float, center_y: float, has_key: bool, alpha: int
    ) -> None:
        size = settings.HUD_STAT_ICON
        arcade.draw_texture_rect(
            self._key_icon,
            XYWH(center_x, center_y, size, size),
            pixelated=True,
            color=WHITE if has_key else self._key_empty,
            alpha=alpha,
        )

    def _draw_ghost_gauge(
        self, right: float, mid_y: float, ratio: float, flash: float, alpha: int
    ) -> None:
        """Jauge timer, alignee a droite sous les stats."""
        fill = (*settings.COLOR_HUD_GHOST_GAUGE, alpha)
        back = (*settings.COLOR_HUD_BAR_BACKGROUND, alpha)
        icon = settings.HUD_GAUGE_ICON
        width = settings.HUD_GAUGE_WIDTH
        height = settings.HUD_GAUGE_HEIGHT
        gap = settings.HUD_GAUGE_GAP
        bar_right = right
        bar_left = right - width
        bottom = mid_y - height / 2
        top = mid_y + height / 2
        icon_x = bar_left - gap - icon / 2
        icon_half = icon / 2
        arcade.draw_lrbt_rectangle_filled(
            icon_x - icon_half,
            icon_x + icon_half,
            mid_y - icon_half,
            mid_y + icon_half,
            back,
        )
        arcade.draw_lrbt_rectangle_outline(
            icon_x - icon_half,
            icon_x + icon_half,
            mid_y - icon_half,
            mid_y + icon_half,
            fill,
            1,
        )
        self._draw_ghost_icon(icon_x, mid_y, fill, size=icon)
        arcade.draw_lrbt_rectangle_filled(bar_left, bar_right, bottom, top, back)
        if ratio > 0.0:
            arcade.draw_lrbt_rectangle_filled(
                bar_left, bar_left + width * ratio, bottom, top, fill
            )
        arcade.draw_lrbt_rectangle_outline(bar_left, bar_right, bottom, top, fill, 1)
        if flash > 0.0:
            pad = 1 + 5 * flash
            arcade.draw_lrbt_rectangle_outline(
                bar_left - pad,
                bar_right + pad,
                bottom - pad,
                top + pad,
                (*settings.COLOR_HUD_GHOST_GAUGE, int(220 * flash * alpha / 255)),
                2,
            )

    def _draw_ghost_icon(
        self,
        center_x: float,
        center_y: float,
        color: tuple[int, int, int] | tuple[int, int, int, int] | None = None,
        *,
        size: float | None = None,
    ) -> None:
        """Losange d'ame, plus un noyau clair."""
        fill = color if color is not None else settings.COLOR_HUD_GHOST_GAUGE
        extent = (size if size is not None else settings.HUD_STAT_ICON) * 0.42
        core = extent * 0.42
        arcade.draw_triangle_filled(
            center_x,
            center_y + extent,
            center_x - extent,
            center_y,
            center_x + extent,
            center_y,
            fill,
        )
        arcade.draw_triangle_filled(
            center_x,
            center_y - extent,
            center_x - extent,
            center_y,
            center_x + extent,
            center_y,
            fill,
        )
        arcade.draw_triangle_filled(
            center_x,
            center_y + core,
            center_x - core,
            center_y,
            center_x + core,
            center_y,
            settings.COLOR_TRAIL_GHOST_CORE,
        )
        arcade.draw_triangle_filled(
            center_x,
            center_y - core,
            center_x - core,
            center_y,
            center_x + core,
            center_y,
            settings.COLOR_TRAIL_GHOST_CORE,
        )
