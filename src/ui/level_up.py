"""Overlay de choix d'amelioration fantome : 3 cartes, un choix, force.

Declenche par `PlayView` a chaque montee de niveau (voir `_collect` dans
`src/systems/game_state.py`). Le niveau reste charge et fige derriere,
comme la pause (`src/ui/pause.py`), mais l'accent est bleu-spectre plutot
que marron/torche pour bien distinguer "recompense" de "pause" au premier
coup d'oeil. Pas de bouton "annuler" : une carte doit etre choisie.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import arcade

import settings
from src.systems.upgrades import UpgradeCard
from src.ui.display import handle_display_key
from src.ui.fonts import PIXEL_FONT
from src.ui.menu_kit import draw_panel


class _CardButton:
    """Une carte d'amelioration : titre, effet, prix. Focus clavier + survol souris."""

    def __init__(self, card: UpgradeCard, *, on_activate: Callable[[str], None]) -> None:
        self.card = card
        self.on_activate = on_activate
        self.focused = False
        self.hovered = False
        self._pressed = False
        self.left = self.right = self.bottom = self.top = 0.0
        text_width = settings.MENU_CARD_WIDTH - 24
        self.title = arcade.Text(
            card.name,
            0,
            0,
            settings.COLOR_CARD_ACCENT,
            font_size=11,
            anchor_x="center",
            anchor_y="center",
            align="center",
            font_name=PIXEL_FONT,
            width=text_width,
            multiline=True,
        )
        self.description = arcade.Text(
            card.description,
            0,
            0,
            settings.COLOR_HUD_TEXT,
            font_size=9,
            anchor_x="center",
            anchor_y="center",
            align="center",
            font_name=PIXEL_FONT,
            width=text_width,
            multiline=True,
        )
        self.rank = arcade.Text(
            f"rang {card.rank + 1}",
            0,
            0,
            settings.COLOR_MENU_HINT,
            font_size=8,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        self.cost = arcade.Text(
            f"{card.cost} ame" + ("s" if card.cost != 1 else ""),
            0,
            0,
            settings.COLOR_CARD_COST,
            font_size=11,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )

    def place(self, center_x: float, center_y: float, width: float, height: float) -> None:
        self.left = center_x - width / 2
        self.right = center_x + width / 2
        self.bottom = center_y - height / 2
        self.top = center_y + height / 2
        self.title.x = center_x
        self.title.y = self.top - 34
        self.description.x = center_x
        self.description.y = center_y + 8
        self.rank.x = center_x
        self.rank.y = self.bottom + 42
        self.cost.x = center_x
        self.cost.y = self.bottom + 20

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and self.bottom <= y <= self.top

    def on_hover(self, x: float, y: float) -> None:
        self.hovered = self.contains(x, y)

    def on_press(self, x: float, y: float) -> bool:
        if not self.contains(x, y):
            return False
        self._pressed = True
        return True

    def on_release(self, x: float, y: float) -> bool:
        was_pressed = self._pressed
        self._pressed = False
        if was_pressed and self.contains(x, y):
            self.activate()
            return True
        return False

    def activate(self) -> None:
        self.on_activate(self.card.kind)

    def draw(self) -> None:
        active = self.focused or self.hovered
        fill = settings.COLOR_CARD_FOCUS_FILL if active else settings.COLOR_CARD_FILL
        border = settings.COLOR_CARD_ACCENT if active else settings.COLOR_CARD_BORDER
        if self._pressed:
            fill = settings.COLOR_MENU_PANEL
        draw_panel(
            self.left,
            self.right,
            self.bottom,
            self.top,
            fill=fill,
            border=border,
            accent=settings.COLOR_CARD_ACCENT if active else None,
        )
        self.title.draw()
        self.description.draw()
        self.rank.draw()
        self.cost.draw()


class LevelUpOverlay:
    """Voile + panneau + rangee de cartes. Choix force, pas d'annulation."""

    def __init__(self, *, on_choose: Callable[[str], None]) -> None:
        self._on_choose = on_choose
        self.title = arcade.Text(
            "MONTEE DE NIVEAU",
            0,
            0,
            settings.COLOR_MENU_TITLE,
            font_size=18,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        self.hint = arcade.Text(
            "Choisis une amelioration pour le fantome",
            0,
            0,
            settings.COLOR_MENU_HINT,
            font_size=10,
            anchor_x="center",
            font_name=PIXEL_FONT,
        )
        self.cards: list[_CardButton] = []
        self.focus_index = 0
        self._input_lock = 0.0
        self._layout_w = 0.0
        self._layout_h = 0.0
        self._panel = (0.0, 0.0, 0.0, 0.0)

    def set_cards(self, cards: Sequence[UpgradeCard]) -> None:
        self.cards = [_CardButton(card, on_activate=self._activate) for card in cards]
        self.focus_index = 0
        self._input_lock = settings.MENU_LEVEL_UP_INPUT_LOCK
        self._sync()
        self._layout_w = self._layout_h = -1.0  # force un relayout au prochain draw

    def _sync(self) -> None:
        for index, card in enumerate(self.cards):
            card.focused = index == self.focus_index

    def layout(self, width: float, height: float) -> None:
        if width == self._layout_w and height == self._layout_h:
            return
        self._layout_w = width
        self._layout_h = height
        card_w = settings.MENU_CARD_WIDTH
        card_h = settings.MENU_CARD_HEIGHT
        gap = settings.MENU_CARD_GAP
        count = max(1, len(self.cards))
        row_w = count * card_w + (count - 1) * gap
        panel_w = row_w + 80.0
        panel_h = card_h + 170.0
        cx, cy = width / 2, height / 2
        left, right = cx - panel_w / 2, cx + panel_w / 2
        bottom, top = cy - panel_h / 2, cy + panel_h / 2
        self._panel = (left, right, bottom, top)
        self.title.x = cx
        self.title.y = top - 36
        self.hint.x = cx
        self.hint.y = bottom + 22
        row_y = cy - 6
        left0 = cx - row_w / 2
        for index, card in enumerate(self.cards):
            card_cx = left0 + index * (card_w + gap) + card_w / 2
            card.place(card_cx, row_y, card_w, card_h)

    def _activate(self, kind: str) -> None:
        if self._input_lock > 0.0:
            return
        self._on_choose(kind)

    def update(self, delta_time: float) -> None:
        """Compte le delai pendant lequel les entrees sont ignorees."""
        self._input_lock = max(0.0, self._input_lock - max(0.0, delta_time))

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
        draw_panel(left, right, bottom, top, accent=settings.COLOR_CARD_ACCENT)
        self.title.draw()
        self.hint.draw()
        for card in self.cards:
            card.draw()

    def on_key_press(self, window: arcade.Window, symbol: int, modifiers: int) -> None:
        if handle_display_key(window, symbol, modifiers):
            return
        if self._input_lock > 0.0 or not self.cards:
            return
        if symbol in (arcade.key.LEFT, arcade.key.A):
            self.focus_index = (self.focus_index - 1) % len(self.cards)
            self._sync()
        elif symbol in (arcade.key.RIGHT, arcade.key.D):
            self.focus_index = (self.focus_index + 1) % len(self.cards)
            self._sync()
        elif symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER, arcade.key.SPACE):
            self.cards[self.focus_index].activate()

    def on_mouse_motion(self, x: float, y: float) -> None:
        for index, card in enumerate(self.cards):
            card.on_hover(x, y)
            if card.hovered:
                self.focus_index = index
        self._sync()

    def on_mouse_press(self, x: float, y: float) -> None:
        if self._input_lock > 0.0:
            return
        for card in self.cards:
            card.on_press(x, y)

    def on_mouse_release(self, x: float, y: float) -> None:
        if self._input_lock > 0.0:
            return
        for card in self.cards:
            card.on_release(x, y)
