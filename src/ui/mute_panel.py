"""Overlay "Son" : coupe/reactive les 4 pistes de `src.ui.music`.

Meme forme que `PauseMenu` (`src/ui/pause.py`) - voile + panneau + colonne de
boutons - pour pouvoir s'ouvrir aussi bien depuis le menu principal
(`TitleView`) que depuis le menu pause en jeu (`PlayView`), sans dupliquer le
code. Contrairement a un `TextButton` normal, chaque bouton ici porte l'etat
ON/OFF de sa piste dans son propre libelle : `menu_kit.TextButton` n'a pas de
`set_caption()`, donc on modifie directement `button.label.text`.
"""

from __future__ import annotations

from collections.abc import Callable

import arcade

import settings
from src.ui.display import handle_display_key
from src.ui.fonts import PIXEL_FONT
from src.ui.menu_kit import ButtonColumn, TextButton, draw_panel
from src.ui.music import MUTABLE_TRACKS, music


def _caption(label: str, kind: str) -> str:
    return f"{label} : {'OFF' if music.is_muted(kind) else 'ON'}"


class MutePanel:
    """Voile + panneau : un bouton par piste, plus un retour."""

    def __init__(self, *, on_close: Callable[[], None]) -> None:
        self.on_close = on_close
        self.title = arcade.Text(
            "SON",
            0,
            0,
            settings.COLOR_MENU_TITLE,
            font_size=18,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        self.hint = arcade.Text(
            "Echap pour revenir",
            0,
            0,
            settings.COLOR_MENU_HINT,
            font_size=10,
            anchor_x="center",
            font_name=PIXEL_FONT,
        )
        self.column = ButtonColumn()
        self._track_buttons: dict[str, TextButton] = {}
        self._layout_w = 0.0
        self._layout_h = 0.0
        self._panel = (0.0, 0.0, 0.0, 0.0)
        self._build_buttons()

    def _build_buttons(self) -> None:
        """Une seule fois : les boutons gardent leur etat (caption) entre deux
        `layout()`, contrairement a `PauseMenu` qui peut se permettre de tout
        reconstruire (ses libelles sont fixes)."""
        buttons: list[TextButton] = []
        for kind, label in MUTABLE_TRACKS:
            button = TextButton(_caption(label, kind), on_activate=lambda kind=kind: self._toggle(kind))
            self._track_buttons[kind] = button
            buttons.append(button)
        buttons.append(TextButton("Retour", on_activate=self.on_close))
        self.column.set_buttons(buttons)

    def _toggle(self, kind: str) -> None:
        music.set_muted(kind, not music.is_muted(kind))
        label = dict(MUTABLE_TRACKS)[kind]
        self._track_buttons[kind].label.text = _caption(label, kind)

    def layout(self, width: float, height: float) -> None:
        if width == self._layout_w and height == self._layout_h:
            return
        self._layout_w = width
        self._layout_h = height
        panel_w, panel_h = 380.0, 380.0
        cx, cy = width / 2, height / 2
        left, right = cx - panel_w / 2, cx + panel_w / 2
        bottom, top = cy - panel_h / 2, cy + panel_h / 2
        self._panel = (left, right, bottom, top)
        self.title.x = cx
        self.title.y = top - 40
        self.hint.x = cx
        self.hint.y = bottom + 24
        self.column.layout(cx, self.title.y - 56)

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
        self.hint.draw()

    def on_key_press(self, window: arcade.Window, symbol: int, modifiers: int) -> None:
        if handle_display_key(window, symbol, modifiers):
            return
        if symbol == arcade.key.ESCAPE:
            self.on_close()
            return
        self.column.on_key_press(symbol)

    def on_mouse_motion(self, x: float, y: float) -> None:
        self.column.on_mouse_motion(x, y)

    def on_mouse_press(self, x: float, y: float) -> None:
        self.column.on_mouse_press(x, y)

    def on_mouse_release(self, x: float, y: float) -> None:
        self.column.on_mouse_release(x, y)
