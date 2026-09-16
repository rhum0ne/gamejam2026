"""Widgets de menu dessines a la main (pas de pack de sprites).

Rectangles + `arcade.Text` crees une fois. Accent marron / torche pour le
focus, or pour la victoire.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import arcade

import settings
from src.ui.fonts import PIXEL_FONT

_Activate = Callable[[], None]


def draw_panel(
    left: float,
    right: float,
    bottom: float,
    top: float,
    *,
    fill: tuple[int, int, int] = settings.COLOR_MENU_PANEL,
    border: tuple[int, int, int] = settings.COLOR_MENU_PANEL_BORDER,
    accent: tuple[int, int, int] | None = None,
) -> None:
    """Carte sombre a bord fin, filet d'accent optionnel en haut."""
    arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, fill)
    arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, border, 2)
    if accent is not None:
        arcade.draw_lrbt_rectangle_filled(left, right, top - 4, top, accent)


class TextButton:
    """Bouton texte : idle / focus / press, clavier et souris."""

    def __init__(self, caption: str, *, on_activate: _Activate | None = None) -> None:
        self.caption = caption
        self.on_activate = on_activate
        self.focused = False
        self.hovered = False
        self._pressed = False
        self.left = 0.0
        self.right = 0.0
        self.bottom = 0.0
        self.top = 0.0
        self.label = arcade.Text(
            caption,
            0,
            0,
            settings.COLOR_HUD_TEXT,
            font_size=12,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )

    def place(self, center_x: float, center_y: float, width: float, height: float) -> None:
        self.left = center_x - width / 2
        self.right = center_x + width / 2
        self.bottom = center_y - height / 2
        self.top = center_y + height / 2
        self.label.x = center_x
        self.label.y = center_y

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and self.bottom <= y <= self.top

    def set_focused(self, focused: bool) -> None:
        self.focused = focused

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
        if self.on_activate is not None:
            self.on_activate()

    def draw(self) -> None:
        active = self.focused or self.hovered
        fill = settings.COLOR_MENU_FOCUS_FILL if active else settings.COLOR_MENU_CELL
        border = settings.COLOR_MENU_FOCUS if active else settings.COLOR_MENU_CELL_BORDER
        if self._pressed:
            fill = settings.COLOR_MENU_PANEL
        arcade.draw_lrbt_rectangle_filled(self.left, self.right, self.bottom, self.top, fill)
        arcade.draw_lrbt_rectangle_outline(self.left, self.right, self.bottom, self.top, border, 2)
        self.label.color = settings.COLOR_MENU_FOCUS if active else settings.COLOR_HUD_TEXT
        self.label.draw()


class LevelCell:
    """Une case du tableau de niveaux : numero, nom au survol via le parent."""

    def __init__(self, index: int, name: str, *, on_activate: _Activate) -> None:
        self.index = index
        self.name = name
        self.on_activate = on_activate
        self.focused = False
        self.hovered = False
        self._pressed = False
        self.left = 0.0
        self.right = 0.0
        self.bottom = 0.0
        self.top = 0.0
        self.number = arcade.Text(
            str(index + 1),
            0,
            0,
            settings.COLOR_HUD_TEXT,
            font_size=22,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )

    def place(self, left: float, right: float, bottom: float, top: float) -> None:
        self.left, self.right, self.bottom, self.top = left, right, bottom, top
        self.number.x = (left + right) / 2
        self.number.y = (bottom + top) / 2

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and self.bottom <= y <= self.top

    def activate(self) -> None:
        self.on_activate()

    def draw(self) -> None:
        active = self.focused or self.hovered
        fill = settings.COLOR_MENU_FOCUS_FILL if active else settings.COLOR_MENU_CELL
        border = settings.COLOR_MENU_FOCUS if active else settings.COLOR_MENU_CELL_BORDER
        arcade.draw_lrbt_rectangle_filled(self.left, self.right, self.bottom, self.top, fill)
        arcade.draw_lrbt_rectangle_outline(self.left, self.right, self.bottom, self.top, border, 2)
        if active:
            arcade.draw_lrbt_rectangle_filled(
                self.left, self.left + 6, self.bottom, self.top, settings.COLOR_MENU_FOCUS
            )
        self.number.color = settings.COLOR_MENU_FOCUS if active else settings.COLOR_HUD_TEXT
        self.number.draw()


class LevelGrid:
    """Tableau de cases (lignes x colonnes), navigation 2D."""

    def __init__(self, cells: Sequence[LevelCell], columns: int) -> None:
        if columns <= 0:
            raise ValueError("columns doit etre strictement positif")
        self.cells = list(cells)
        self.columns = columns
        self.focus_index = 0
        if self.cells:
            self.cells[0].focused = True

    def layout(
        self,
        center_x: float,
        top_y: float,
        cell_width: float | None = None,
        cell_height: float | None = None,
    ) -> float:
        """Place la grille. Retourne le y du bas (pour enchainer un bouton)."""
        count = len(self.cells)
        if count == 0:
            return top_y
        cols = self.columns
        rows = (count + cols - 1) // cols
        width = settings.MENU_CELL_WIDTH if cell_width is None else cell_width
        height = settings.MENU_CELL_HEIGHT if cell_height is None else cell_height
        gap = settings.MENU_CELL_GAP
        total_w = cols * width + (cols - 1) * gap
        left0 = center_x - total_w / 2
        for index, cell in enumerate(self.cells):
            row, col = divmod(index, cols)
            left = left0 + col * (width + gap)
            top = top_y - row * (height + gap)
            cell.place(left, left + width, top - height, top)
        return top_y - rows * height - (rows - 1) * gap

    def _sync(self) -> None:
        for index, cell in enumerate(self.cells):
            cell.focused = index == self.focus_index

    def move(self, dx: int, dy: int) -> bool:
        """Deplace le focus. Retourne False s'il faut sortir de la grille (vers le bas)."""
        if not self.cells:
            return True
        cols = self.columns
        count = len(self.cells)
        col = self.focus_index % cols
        row = self.focus_index // cols
        rows = (count + cols - 1) // cols
        if dy > 0 and row >= rows - 1:
            return False
        col = max(0, min(cols - 1, col + dx))
        row = max(0, min(rows - 1, row + dy))
        index = min(count - 1, row * cols + col)
        self.focus_index = index
        self._sync()
        return True

    def focus_last_row(self) -> None:
        if not self.cells:
            return
        cols = self.columns
        rows = (len(self.cells) + cols - 1) // cols
        self.focus_index = min(len(self.cells) - 1, (rows - 1) * cols)
        self._sync()

    def activate_focused(self) -> None:
        if self.cells:
            self.cells[self.focus_index].activate()

    def on_hover(self, x: float, y: float) -> bool:
        hit = False
        for index, cell in enumerate(self.cells):
            inside = cell.contains(x, y)
            cell.hovered = inside
            if inside:
                self.focus_index = index
                hit = True
        if hit:
            self._sync()
        return hit

    def on_press(self, x: float, y: float) -> None:
        for cell in self.cells:
            cell._pressed = cell.contains(x, y)

    def on_release(self, x: float, y: float) -> None:
        for cell in self.cells:
            was = cell._pressed
            cell._pressed = False
            if was and cell.contains(x, y):
                cell.activate()
                return

    def draw(self) -> None:
        for cell in self.cells:
            cell.draw()

    @property
    def focused_name(self) -> str:
        if not self.cells:
            return ""
        return self.cells[self.focus_index].name


class ButtonColumn:
    """Liste verticale de `TextButton`."""

    def __init__(self, buttons: Sequence[TextButton] = ()) -> None:
        self.buttons: list[TextButton] = list(buttons)
        self.focus_index = 0
        if self.buttons:
            self.buttons[0].set_focused(True)

    def set_buttons(self, buttons: Sequence[TextButton]) -> None:
        self.buttons = list(buttons)
        self.focus_index = 0
        self._sync()

    def layout(self, center_x: float, top_y: float, gap: float = 10.0) -> None:
        y = top_y
        height = settings.MENU_BUTTON_HEIGHT
        width = settings.MENU_BUTTON_WIDTH
        for button in self.buttons:
            button.place(center_x, y, width, height)
            y -= height + gap

    def _sync(self) -> None:
        for index, button in enumerate(self.buttons):
            button.set_focused(index == self.focus_index)

    def move(self, delta: int) -> None:
        if not self.buttons:
            return
        self.focus_index = (self.focus_index + delta) % len(self.buttons)
        self._sync()

    def activate_focused(self) -> None:
        if self.buttons:
            self.buttons[self.focus_index].activate()

    def on_key_press(self, symbol: int) -> bool:
        if symbol in (arcade.key.UP, arcade.key.W, arcade.key.Z):
            self.move(-1)
            return True
        if symbol in (arcade.key.DOWN, arcade.key.S):
            self.move(1)
            return True
        if symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER, arcade.key.SPACE):
            self.activate_focused()
            return True
        return False

    def on_mouse_motion(self, x: float, y: float) -> None:
        for index, button in enumerate(self.buttons):
            button.on_hover(x, y)
            if button.hovered:
                self.focus_index = index
        self._sync()

    def on_mouse_press(self, x: float, y: float) -> None:
        for button in self.buttons:
            button.on_press(x, y)

    def on_mouse_release(self, x: float, y: float) -> None:
        for button in self.buttons:
            button.on_release(x, y)

    def draw(self) -> None:
        for button in self.buttons:
            button.draw()
