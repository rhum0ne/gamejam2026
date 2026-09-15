"""Panneau lateral de l'editeur : palette d'elements placables.

Le panneau se construit tout seul a partir de `palette.PALETTE` : chaque
categorie devient un titre, chaque element une ligne cliquable avec sa
vignette, son symbole de legende et le nombre de fois qu'il apparait dans la
carte. Ajouter une tuile au jeu la fait apparaitre ici sans rien changer.
"""

from __future__ import annotations

from dataclasses import dataclass

import arcade
from arcade.types import XYWH

import settings
from src.editor import icons, palette
from src.editor.palette import PaletteItem
from src.ui import labels


@dataclass(frozen=True, slots=True)
class _Row:
    """Une ligne du panneau : titre de categorie ou element."""

    label: str
    item: PaletteItem | None
    height: float


class PalettePanel:
    """Liste deroulante des elements placables, a droite de l'ecran."""

    def __init__(self) -> None:
        self._rows = self._build_rows()
        self._scroll = 0.0
        self._left = 0.0
        self._bottom = 0.0
        self._width = float(settings.EDITOR_PANEL_WIDTH)
        self._height = float(settings.EDITOR_WINDOW_HEIGHT)
        self._title = labels.Line(settings.EDITOR_TITLE_SIZE, settings.COLOR_EDITOR_ACCENT)
        self._texts: dict[str, labels.Line] = {}
        self._counts: dict[str, labels.Line] = {}

    @staticmethod
    def _build_rows() -> tuple[_Row, ...]:
        rows: list[_Row] = []
        for category in palette.CATEGORIES:
            rows.append(_Row(category.upper(), None, settings.EDITOR_ROW_HEIGHT * 0.8))
            for item in palette.items_in(category):
                rows.append(_Row(item.label, item, settings.EDITOR_ROW_HEIGHT))
        return tuple(rows)

    # ------------------------------------------------------------------ #
    # Geometrie
    # ------------------------------------------------------------------ #

    def layout(self, window_width: float, window_height: float) -> None:
        """Cale le panneau contre le bord droit, au-dessus de la barre d'etat."""
        self._width = float(settings.EDITOR_PANEL_WIDTH)
        self._left = window_width - self._width
        self._bottom = float(settings.EDITOR_STATUS_HEIGHT)
        self._height = max(1.0, window_height - self._bottom)
        self._clamp_scroll()

    @property
    def left(self) -> float:
        return self._left

    @property
    def width(self) -> float:
        return self._width

    def contains(self, x: float, y: float) -> bool:
        return x >= self._left and y >= self._bottom

    def scroll_by(self, lines: float) -> None:
        self._scroll -= lines * settings.EDITOR_ROW_HEIGHT
        self._clamp_scroll()

    def item_at(self, x: float, y: float) -> PaletteItem | None:
        """Element sous le curseur, ou None (titre de categorie, hors panneau)."""
        if not self.contains(x, y):
            return None
        top = self._bottom + self._height - settings.EDITOR_ROW_HEIGHT * 1.4 + self._scroll
        for row in self._rows:
            row_top = top
            top -= row.height
            if top <= y <= row_top and row.item is not None:
                return row.item
        return None

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #

    def draw(self, current_kind: str, counts: dict[str, int], hover_x: float, hover_y: float) -> None:
        """Dessine le panneau ; `current_kind` est surligne."""
        right = self._left + self._width
        panel_top = self._bottom + self._height
        arcade.draw_lrbt_rectangle_filled(
            self._left, right, self._bottom, panel_top, settings.COLOR_EDITOR_PANEL
        )
        arcade.draw_line(
            self._left, self._bottom, self._left, panel_top, settings.COLOR_EDITOR_PANEL_BORDER, 2
        )
        self._title.draw("PALETTE", self._left + 14, panel_top - 26)
        hovered = self.item_at(hover_x, hover_y)
        top = panel_top - settings.EDITOR_ROW_HEIGHT * 1.4 + self._scroll
        for row in self._rows:
            row_top = top
            top -= row.height
            if row_top < self._bottom or top > panel_top:
                continue
            if row.item is None:
                self._line(f"cat:{row.label}", settings.COLOR_EDITOR_TEXT_DIM).draw(
                    row.label, self._left + 14, top + row.height * 0.35
                )
                continue
            self._draw_item(row, top, row_top, current_kind, counts, hovered)

    def _draw_item(
        self,
        row: _Row,
        bottom: float,
        top: float,
        current_kind: str,
        counts: dict[str, int],
        hovered: PaletteItem | None,
    ) -> None:
        item = row.item
        assert item is not None  # garanti par l'appelant
        right = self._left + self._width
        if item.kind == current_kind:
            arcade.draw_lrbt_rectangle_filled(
                self._left + 2, right, bottom, top, settings.COLOR_EDITOR_ROW_ACTIVE
            )
        elif hovered is item:
            arcade.draw_lrbt_rectangle_filled(
                self._left + 2, right, bottom, top, settings.COLOR_EDITOR_ROW_HOVER
            )
        middle = (bottom + top) / 2
        swatch = settings.EDITOR_SWATCH_SIZE
        arcade.draw_texture_rect(
            icons.cell_texture(item, swatch),
            XYWH(self._left + 14 + swatch / 2, middle, swatch, swatch),
            pixelated=True,
        )
        color = (
            settings.COLOR_EDITOR_TEXT
            if item.kind == current_kind
            else settings.COLOR_EDITOR_TEXT_DIM
        )
        self._line(item.kind, color).draw(
            f"{item.symbol} {item.label}"[:26], self._left + 20 + swatch, middle - 4, color
        )
        total = counts.get(item.kind, 0)
        self._count(item.kind).draw(
            str(total) if total else "-",
            right - 14,
            middle - 4,
            settings.COLOR_EDITOR_ACCENT if total else settings.COLOR_EDITOR_PANEL_BORDER,
        )

    def _line(self, key: str, color: tuple[int, int, int]) -> labels.Line:
        text = self._texts.get(key)
        if text is None:
            text = labels.Line(settings.EDITOR_TEXT_SIZE, color)
            self._texts[key] = text
        return text

    def _count(self, key: str) -> labels.Line:
        text = self._counts.get(key)
        if text is None:
            text = labels.Line(
                settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_ACCENT, anchor_x="right"
            )
            self._counts[key] = text
        return text

    def _clamp_scroll(self) -> None:
        content = sum(row.height for row in self._rows) + settings.EDITOR_ROW_HEIGHT * 2
        maximum = max(0.0, content - self._height)
        self._scroll = max(0.0, min(maximum, self._scroll))
