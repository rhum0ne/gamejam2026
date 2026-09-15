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
    _BAR_WIDTH = 320
    _BAR_HEIGHT = 14

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
        self._timer_text = self._make_text(
            "", screen_width / 2, screen_height - 52, size=13, anchor_x="center"
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
            self._draw_dash_gauge(data)
        if data.ghost_time_left is not None:
            self._draw_ghost_gauges(data)

    def _draw_dash_gauge(self, data: HudData) -> None:
        """Petite jauge de recharge du dash, en bas a droite."""
        width, height = 88, 8
        right = self.screen_width - self._MARGIN
        left = right - width
        bottom = self._MARGIN + settings.UI_KEY_ICON_HEIGHT + 12
        top = bottom + height
        ratio = max(0.0, min(1.0, data.dash_ratio or 0.0))
        arcade.draw_lrbt_rectangle_filled(
            left, right, bottom, top, settings.COLOR_HUD_BAR_BACKGROUND
        )
        fill_color = settings.COLOR_DASH if data.dash_ready else settings.COLOR_DASH_GAUGE
        if ratio > 0.0:
            arcade.draw_lrbt_rectangle_filled(
                left, left + width * ratio, bottom, top, fill_color
            )
        if data.dash_flash > 0.0:
            pad = 2 + 6 * data.dash_flash
            arcade.draw_lrbt_rectangle_outline(
                left - pad,
                right + pad,
                bottom - pad,
                top + pad,
                (*settings.COLOR_DASH, int(230 * data.dash_flash)),
                2,
            )
        elif data.dash_ready:
            arcade.draw_lrbt_rectangle_outline(
                left - 1, right + 1, bottom - 1, top + 1, settings.COLOR_DASH, 1
            )

    def _draw_ghost_gauges(self, data: HudData) -> None:
        """Jauge de temps restant du fantome et tension de la longe."""
        time_left = max(0.0, data.ghost_time_left or 0.0)
        ratio = time_left / data.ghost_duration if data.ghost_duration else 0.0
        center_x = self.screen_width / 2
        left = center_x - self._BAR_WIDTH / 2
        top = self.screen_height - self._MARGIN - 6
        bottom = top - self._BAR_HEIGHT

        arcade.draw_lrbt_rectangle_filled(
            left, left + self._BAR_WIDTH, bottom, top, settings.COLOR_HUD_BAR_BACKGROUND
        )
        arcade.draw_lrbt_rectangle_filled(
            left, left + self._BAR_WIDTH * ratio, bottom, top, settings.COLOR_HUD_BAR_FILL
        )
        self._timer_text.text = f"Retour au corps dans {time_left:0.1f} s"
        self._timer_text.draw()

        if data.leash_ratio > 0.75:
            arcade.draw_lrbt_rectangle_outline(
                left - 3, left + self._BAR_WIDTH + 3, bottom - 3, top + 3, settings.COLOR_SPIKE, 2
            )
