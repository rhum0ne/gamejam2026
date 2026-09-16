"""Panneau lateral de l'editeur : plaques, puis palette d'elements placables.

Le panneau se construit tout seul a partir de `palette.PALETTE` : chaque
categorie devient un titre, chaque element une ligne cliquable avec sa
vignette, son symbole de legende et le nombre de fois qu'il apparait dans la
carte. Ajouter une tuile au jeu la fait apparaitre ici sans rien changer.

Les plaques d'activation ne sont pas des tuiles : elles sont listees au-dessus,
cliquables pour les selectionner, et se dessinent aussi sur la grille.
"""

from __future__ import annotations

from dataclasses import dataclass

import arcade
from arcade.types import XYWH

import settings
from src.editor import icons, palette
from src.editor.activators import Activator
from src.editor.palette import PaletteItem
from src.ui import labels


@dataclass(frozen=True, slots=True)
class _Row:
    """Une ligne du panneau : titre, element, plaque, ou hint."""

    label: str
    height: float
    item: PaletteItem | None = None
    activator_index: int | None = None
    heading: bool = False
    hint: bool = False


@dataclass(frozen=True, slots=True)
class PanelHit:
    """Cible sous le curseur dans le panneau."""

    item: PaletteItem | None = None
    activator_index: int | None = None


class PalettePanel:
    """Liste deroulante des plaques et des elements placables, a droite."""

    def __init__(self) -> None:
        self._palette_rows = self._build_palette_rows()
        self._scroll = 0.0
        self._left = 0.0
        self._bottom = 0.0
        self._width = float(settings.EDITOR_PANEL_WIDTH)
        self._height = float(settings.EDITOR_WINDOW_HEIGHT)
        self._title = labels.Line(settings.EDITOR_TITLE_SIZE, settings.COLOR_EDITOR_ACCENT)
        self._texts: dict[str, labels.Line] = {}
        self._counts: dict[str, labels.Line] = {}

    @staticmethod
    def _build_palette_rows() -> tuple[_Row, ...]:
        rows: list[_Row] = []
        for category in palette.CATEGORIES:
            rows.append(
                _Row(category.upper(), settings.EDITOR_ROW_HEIGHT * 0.85, heading=True)
            )
            for item in palette.items_in(category):
                rows.append(_Row(item.label, settings.EDITOR_ROW_HEIGHT, item=item))
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

    def hit(self, x: float, y: float, activators: tuple[Activator, ...]) -> PanelHit | None:
        """Ligne cliquable sous le curseur, ou None."""
        if not self.contains(x, y):
            return None
        top = self._list_top()
        for row in self._rows(activators):
            row_top = top
            top -= row.height
            if not (top <= y <= row_top):
                continue
            if row.item is not None:
                return PanelHit(item=row.item)
            if row.activator_index is not None:
                return PanelHit(activator_index=row.activator_index)
            return None
        return None

    def item_at(self, x: float, y: float) -> PaletteItem | None:
        """Compat : element de palette sous le curseur, sans les plaques."""
        hit = self.hit(x, y, ())
        return hit.item if hit is not None else None

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #

    def draw(
        self,
        current_kind: str,
        counts: dict[str, int],
        hover_x: float,
        hover_y: float,
        activators: tuple[Activator, ...] = (),
        selected_activator: int | None = None,
        plate_tool: bool = False,
    ) -> None:
        """Dessine le panneau ; `current_kind` et la plaque active sont surlignes."""
        right = self._left + self._width
        panel_top = self._bottom + self._height
        arcade.draw_lrbt_rectangle_filled(
            self._left, right, self._bottom, panel_top, settings.COLOR_EDITOR_PANEL
        )
        arcade.draw_line(
            self._left, self._bottom, self._left, panel_top, settings.COLOR_EDITOR_PANEL_BORDER, 2
        )
        self._title.draw("OUTILS", self._left + 16, panel_top - 28)
        hovered = self.hit(hover_x, hover_y, activators)
        rows = self._rows(activators)
        self._clamp_scroll(sum(row.height for row in rows))
        top = self._list_top()
        for row in rows:
            row_top = top
            top -= row.height
            if row_top < self._bottom or top > panel_top:
                continue
            if row.heading:
                self._draw_heading(row, top, row_top)
                continue
            if row.hint:
                self._line(f"hint:{row.label}", settings.COLOR_EDITOR_TEXT_DIM).draw(
                    row.label,
                    self._left + 16,
                    top + row.height * 0.28,
                    settings.COLOR_EDITOR_TEXT_DIM,
                    max_width=self._width - 32,
                )
                continue
            if row.activator_index is not None:
                self._draw_plate_row(
                    row,
                    activators[row.activator_index],
                    top,
                    row_top,
                    selected_activator,
                    hovered,
                    plate_tool,
                )
                continue
            self._draw_item(row, top, row_top, current_kind, counts, hovered)

    def _draw_heading(self, row: _Row, bottom: float, top: float) -> None:
        right = self._left + self._width
        arcade.draw_lrbt_rectangle_filled(
            self._left + 2, right - 2, bottom, top, settings.COLOR_EDITOR_HEADING
        )
        self._line(f"cat:{row.label}", settings.COLOR_EDITOR_ACCENT).draw(
            row.label, self._left + 16, bottom + row.height * 0.28, settings.COLOR_EDITOR_ACCENT
        )

    def _draw_plate_row(
        self,
        row: _Row,
        activator: Activator,
        bottom: float,
        top: float,
        selected_index: int | None,
        hovered: PanelHit | None,
        plate_tool: bool,
    ) -> None:
        index = row.activator_index
        assert index is not None
        right = self._left + self._width
        active = selected_index == index and plate_tool
        if active:
            arcade.draw_lrbt_rectangle_filled(
                self._left + 2, right, bottom, top, settings.COLOR_EDITOR_ROW_ACTIVE
            )
        elif hovered is not None and hovered.activator_index == index:
            arcade.draw_lrbt_rectangle_filled(
                self._left + 2, right, bottom, top, settings.COLOR_EDITOR_ROW_HOVER
            )
        middle = (bottom + top) / 2
        color = settings.COLOR_EDITOR_TEXT if active else settings.COLOR_EDITOR_TEXT_DIM
        self._line(f"plate:{index}", color).draw(
            row.label,
            self._left + 16,
            middle - 6,
            color,
            max_width=self._width - 72,
        )
        total = len(activator.targets)
        self._count(f"plate:{index}").draw(
            str(total),
            right - 16,
            middle - 6,
            settings.COLOR_EDITOR_ACCENT if total else settings.COLOR_EDITOR_WARNING,
        )

    def _draw_item(
        self,
        row: _Row,
        bottom: float,
        top: float,
        current_kind: str,
        counts: dict[str, int],
        hovered: PanelHit | None,
    ) -> None:
        item = row.item
        assert item is not None  # garanti par l'appelant
        right = self._left + self._width
        if item.kind == current_kind:
            arcade.draw_lrbt_rectangle_filled(
                self._left + 2, right, bottom, top, settings.COLOR_EDITOR_ROW_ACTIVE
            )
        elif hovered is not None and hovered.item is item:
            arcade.draw_lrbt_rectangle_filled(
                self._left + 2, right, bottom, top, settings.COLOR_EDITOR_ROW_HOVER
            )
        middle = (bottom + top) / 2
        swatch = settings.EDITOR_SWATCH_SIZE
        arcade.draw_texture_rect(
            icons.cell_texture(item, swatch),
            XYWH(self._left + 16 + swatch / 2, middle, swatch, swatch),
            pixelated=True,
        )
        color = (
            settings.COLOR_EDITOR_TEXT
            if item.kind == current_kind
            else settings.COLOR_EDITOR_TEXT_DIM
        )
        label_x = self._left + 24 + swatch
        self._line(item.kind, color).draw(
            f"{item.symbol}  {item.label}",
            label_x,
            middle - 6,
            color,
            max_width=right - 56 - label_x,
        )
        total = counts.get(item.kind, 0)
        self._count(item.kind).draw(
            str(total) if total else "-",
            right - 16,
            middle - 6,
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

    def _rows(self, activators: tuple[Activator, ...]) -> tuple[_Row, ...]:
        rows: list[_Row] = [
            _Row("PLAQUES", settings.EDITOR_ROW_HEIGHT * 0.85, heading=True),
        ]
        if not activators:
            rows.append(
                _Row(
                    "L : placer une plaque",
                    settings.EDITOR_ROW_HEIGHT * 0.75,
                    hint=True,
                )
            )
        else:
            for index, activator in enumerate(activators):
                rows.append(
                    _Row(
                        f"#{index + 1}  {activator.column},{activator.row}  x{activator.width}"
                        f"{'  montre' if activator.inverted else ''}",
                        settings.EDITOR_ROW_HEIGHT,
                        activator_index=index,
                    )
                )
        rows.extend(self._palette_rows)
        return tuple(rows)

    def _list_top(self) -> float:
        return self._bottom + self._height - settings.EDITOR_ROW_HEIGHT * 1.35 + self._scroll

    def _clamp_scroll(self, content: float | None = None) -> None:
        if content is None:
            content = sum(row.height for row in self._palette_rows) + settings.EDITOR_ROW_HEIGHT * 8
        maximum = max(0.0, content + settings.EDITOR_ROW_HEIGHT * 2 - self._height)
        self._scroll = max(0.0, min(maximum, self._scroll))
