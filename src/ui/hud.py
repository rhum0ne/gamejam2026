"""HUD en jeu : compteur d'ames, timer du fantome, icones clavier.

Le HUD est "sans etat" : la vue de jeu construit un `HudData` a chaque frame et
le passe a `Hud.draw()`. Les objets `arcade.Text` sont crees une seule fois
(leur creation est couteuse) puis mis a jour via leur attribut `.text`.

Les invites de commandes sont des icones PNG (`src.ui.keys`) qui passent en
etat enfonce (glyphes bleus) d'apres `HudData.pressed_keys`.

Le HUD se dessine en coordonnees ecran : il faut donc activer la camera UI
(`CameraRig.use_ui()`) avant de l'appeler.
"""

from __future__ import annotations

from dataclasses import dataclass

import arcade

import settings
from src.ui import keys
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
    dash_ratio: float | None = None
    dash_ready: bool = False
    dash_flash: float = 0.0
    controls: str = ""
    pressed_keys: frozenset[int] = frozenset()
    show_esprit: bool = False


class Hud:
    """Affichage des informations de jeu par-dessus la scene."""

    _MARGIN = 16

    def __init__(self, screen_width: int, screen_height: int) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._build_texts()

    def _build_texts(self) -> None:
        screen_width, screen_height = self.screen_width, self.screen_height
        self._level_text = self._make_text("", self._MARGIN, screen_height - 30)
        self._state_text = self._make_text("", self._MARGIN, screen_height - 54, size=13)
        self._essence_text = self._make_text(
            "", screen_width - self._MARGIN, screen_height - 30, anchor_x="right"
        )
        self._key_text = self._make_text(
            "", screen_width - self._MARGIN, screen_height - 54, size=13, anchor_x="right"
        )
        self._hint_text = self._make_text(
            "", screen_width / 2, self._MARGIN + 6, size=13, anchor_x="center"
        )
        self._fps_text = self._make_text(
            "", self._MARGIN, self._MARGIN + 6, size=12, color=settings.COLOR_MENU_HINT
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

    def draw(self, data: HudData) -> None:
        """Dessine le HUD a partir de l'instantane fourni."""
        self._level_text.text = data.level_name
        self._state_text.text = data.state_label
        self._essence_text.text = f"Ames : {data.essence}  |  Fantome niv. {data.ghost_level}"
        self._key_text.text = "Cle : oui" if data.has_key else "Cle : non"
        self._hint_text.text = data.hint

        self._level_text.draw()
        self._state_text.draw()
        self._essence_text.draw()
        self._key_text.draw()
        if data.fps is not None:
            self._fps_text.text = f"{data.fps:.0f} FPS"
            self._fps_text.draw()
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
        if data.dash_ratio is not None:
            flash = data.dash_flash
            fill = settings.COLOR_DASH if data.dash_ready else settings.COLOR_DASH_GAUGE
            self._draw_action_gauge(data.dash_ratio, fill, "dash", flash)
        if data.ghost_time_left is not None:
            duration = max(data.ghost_duration, 0.001)
            ratio = max(0.0, min(1.0, data.ghost_time_left / duration))
            flash = 0.0
            if ratio <= settings.HUD_GAUGE_LOW:
                flash = 0.45 + 0.55 * abs((data.ghost_time_left * 6.0) % 1.0 - 0.5) * 2.0
            self._draw_action_gauge(ratio, settings.COLOR_HUD_GHOST_GAUGE, "ghost", flash)

    def _gauge_geometry(self) -> tuple[float, float, float, float, float, float]:
        """Retourne (icon_x, bar_left, bar_right, bottom, top, icon_half)."""
        icon = settings.HUD_GAUGE_ICON
        width = settings.HUD_GAUGE_WIDTH
        height = settings.HUD_GAUGE_HEIGHT
        gap = settings.HUD_GAUGE_GAP
        total = icon + gap + width
        left = self.screen_width / 2 - total / 2
        bottom = self._MARGIN + settings.UI_KEY_ICON_HEIGHT + settings.HUD_GAUGE_LIFT
        top = bottom + height
        icon_x = left + icon / 2
        bar_left = left + icon + gap
        bar_right = bar_left + width
        icon_half = icon / 2
        return icon_x, bar_left, bar_right, bottom, top, icon_half

    def _draw_action_gauge(
        self,
        ratio: float,
        fill: tuple[int, int, int],
        kind: str,
        flash: float,
    ) -> None:
        """Jauge bas-centre, dash ou fantome, meme gabarit."""
        ratio = max(0.0, min(1.0, ratio))
        icon_x, bar_left, bar_right, bottom, top, icon_half = self._gauge_geometry()
        mid_y = (bottom + top) / 2
        icon_bottom = mid_y - icon_half
        icon_top = mid_y + icon_half
        arcade.draw_lrbt_rectangle_filled(
            icon_x - icon_half,
            icon_x + icon_half,
            icon_bottom,
            icon_top,
            settings.COLOR_HUD_BAR_BACKGROUND,
        )
        arcade.draw_lrbt_rectangle_outline(
            icon_x - icon_half,
            icon_x + icon_half,
            icon_bottom,
            icon_top,
            fill,
            1,
        )
        if kind == "dash":
            self._draw_dash_icon(icon_x, mid_y, fill)
        else:
            self._draw_ghost_icon(icon_x, mid_y, fill)
        arcade.draw_lrbt_rectangle_filled(
            bar_left, bar_right, bottom, top, settings.COLOR_HUD_BAR_BACKGROUND
        )
        if ratio > 0.0:
            arcade.draw_lrbt_rectangle_filled(
                bar_left, bar_left + settings.HUD_GAUGE_WIDTH * ratio, bottom, top, fill
            )
        arcade.draw_lrbt_rectangle_outline(bar_left, bar_right, bottom, top, fill, 1)
        if flash > 0.0:
            pad = 1 + 5 * flash
            arcade.draw_lrbt_rectangle_outline(
                bar_left - pad,
                bar_right + pad,
                bottom - pad,
                top + pad,
                (*fill, int(220 * flash)),
                2,
            )

    def _draw_dash_icon(self, center_x: float, center_y: float, color: tuple[int, int, int]) -> None:
        """Deux chevrons >>."""
        span = settings.HUD_GAUGE_ICON * 0.28
        depth = settings.HUD_GAUGE_ICON * 0.22
        for shift in (-settings.HUD_GAUGE_ICON * 0.16, settings.HUD_GAUGE_ICON * 0.16):
            tip_x = center_x + shift + depth * 0.65
            back_x = center_x + shift - depth
            arcade.draw_triangle_filled(
                tip_x,
                center_y,
                back_x,
                center_y + span,
                back_x,
                center_y - span,
                color,
            )

    def _draw_ghost_icon(self, center_x: float, center_y: float, color: tuple[int, int, int]) -> None:
        """Losange d'ame, plus un noyau clair."""
        size = settings.HUD_GAUGE_ICON * 0.32
        core = size * 0.42
        arcade.draw_triangle_filled(
            center_x,
            center_y + size,
            center_x - size,
            center_y,
            center_x + size,
            center_y,
            color,
        )
        arcade.draw_triangle_filled(
            center_x,
            center_y - size,
            center_x - size,
            center_y,
            center_x + size,
            center_y,
            color,
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
