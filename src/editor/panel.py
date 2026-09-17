"""Panneau lateral de l'editeur : onglets, grille d'elements, plaques.

Le chrome (themes, aide, onglets) reste fixe en haut. Le contenu defile :
une grille compacte par categorie, ou la liste des plaques. Ajouter une
tuile au jeu la fait apparaitre dans l'onglet de sa categorie, sans rien
changer ici.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import arcade
from arcade.types import XYWH

import settings
from src.editor import icons, palette
from src.editor.activators import Activator
from src.editor.palette import PaletteItem
from src.ui import labels
from src.world.themes import theme_ids, theme_label

TAB_PLAQUES = "Plaques"

_TAB_LABEL = {
    palette.CATEGORY_TERRAIN: "Terrain",
    palette.CATEGORY_HAZARD: "Pieges",
    palette.CATEGORY_GAMEPLAY: "Jeu",
    palette.CATEGORY_DECOR: "Decor",
    palette.CATEGORY_UNKNOWN: "Autre",
    TAB_PLAQUES: "Plaques",
}


@dataclass(frozen=True, slots=True)
class PanelHit:
    """Cible sous le curseur dans le panneau."""

    item: PaletteItem | None = None
    activator_index: int | None = None
    invert_index: int | None = None
    delete_index: int | None = None
    tab: str | None = None
    theme: str | None = None
    help: bool = False


class PalettePanel:
    """Onglets + grille d'elements a droite, plaques dans leur propre onglet."""

    def __init__(self) -> None:
        self.tab = palette.CATEGORIES[0] if palette.CATEGORIES else TAB_PLAQUES
        self._scroll = 0.0
        self._left = 0.0
        self._bottom = 0.0
        self._width = float(settings.EDITOR_PANEL_WIDTH)
        self._height = float(settings.EDITOR_WINDOW_HEIGHT)
        self._title = labels.Line(
            settings.EDITOR_TITLE_SIZE,
            settings.COLOR_EDITOR_ACCENT,
            font_name=settings.EDITOR_UI_FONT,
        )
        self._texts: dict[str, labels.Line] = {}
        self._small: dict[str, labels.Line] = {}

    def tabs(self) -> tuple[str, ...]:
        return (*palette.CATEGORIES, TAB_PLAQUES)

    def select_tab(self, tab: str) -> None:
        """Change d'onglet et remet le defilement en haut."""
        if tab not in self.tabs():
            return
        if tab != self.tab:
            self._scroll = 0.0
        self.tab = tab

    def show_kind(self, kind: str) -> None:
        """Ouvre l'onglet qui contient `kind`."""
        if not kind:
            return
        category = palette.item(kind).category
        if category in palette.CATEGORIES:
            self.select_tab(category)

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

    def theme_chip_center(self, theme: str) -> tuple[float, float]:
        """Centre d'une pastille de theme (tests / clics synthetiques)."""
        left, right, bottom, top = self._theme_rect(theme)
        return (left + right) / 2, (bottom + top) / 2

    def tab_center(self, tab: str) -> tuple[float, float]:
        left, right, bottom, top = self._tab_rect(tab)
        return (left + right) / 2, (bottom + top) / 2

    def help_center(self) -> tuple[float, float]:
        left, right, bottom, top = self._help_rect()
        return (left + right) / 2, (bottom + top) / 2

    def hit(self, x: float, y: float, activators: tuple[Activator, ...]) -> PanelHit | None:
        """Cible cliquable sous le curseur, ou None."""
        if not self.contains(x, y):
            return None
        if _inside(x, y, *self._help_rect()):
            return PanelHit(help=True)
        for theme in theme_ids():
            if _inside(x, y, *self._theme_rect(theme)):
                return PanelHit(theme=theme)
        for tab in self.tabs():
            if _inside(x, y, *self._tab_rect(tab)):
                return PanelHit(tab=tab)
        if y > self._content_top():
            return None
        if self.tab == TAB_PLAQUES:
            return self._hit_plates(x, y, activators)
        return self._hit_grid(x, y)

    def item_at(self, x: float, y: float) -> PaletteItem | None:
        """Compat : element de palette sous le curseur."""
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
        current_theme: str = "",
    ) -> None:
        """Dessine le chrome puis le contenu de l'onglet actif."""
        right = self._left + self._width
        panel_top = self._bottom + self._height
        arcade.draw_lrbt_rectangle_filled(
            self._left, right, self._bottom, panel_top, settings.COLOR_EDITOR_PANEL
        )
        arcade.draw_line(
            self._left, self._bottom, self._left, panel_top, settings.COLOR_EDITOR_PANEL_BORDER, 2
        )
        self._draw_chrome(hover_x, hover_y, current_theme)
        hovered = self.hit(hover_x, hover_y, activators)
        if self.tab == TAB_PLAQUES:
            self._draw_plates(activators, selected_activator, hovered, plate_tool)
        else:
            self._draw_grid(current_kind, counts, hovered)

    def _draw_chrome(self, hover_x: float, hover_y: float, current_theme: str) -> None:
        panel_top = self._bottom + self._height
        self._title.draw("OUTILS", self._left + 12, panel_top - 26)
        help_rect = self._help_rect()
        hovered_help = _inside(hover_x, hover_y, *help_rect)
        self._draw_chip(help_rect, "Aide", hovered=hovered_help, active=False)
        for theme in theme_ids():
            rect = self._theme_rect(theme)
            self._draw_chip(
                rect,
                theme_label(theme),
                hovered=_inside(hover_x, hover_y, *rect),
                active=theme == current_theme,
            )
        for tab in self.tabs():
            rect = self._tab_rect(tab)
            self._draw_chip(
                rect,
                _TAB_LABEL.get(tab, tab),
                hovered=_inside(hover_x, hover_y, *rect),
                active=tab == self.tab,
            )
        arcade.draw_line(
            self._left,
            self._content_top(),
            self._left + self._width,
            self._content_top(),
            settings.COLOR_EDITOR_PANEL_BORDER,
            1,
        )

    def _draw_chip(
        self,
        rect: tuple[float, float, float, float],
        text: str,
        *,
        hovered: bool,
        active: bool,
    ) -> None:
        left, right, bottom, top = rect
        if active:
            fill = settings.COLOR_EDITOR_ROW_ACTIVE
            color = settings.COLOR_EDITOR_TEXT
        elif hovered:
            fill = settings.COLOR_EDITOR_ROW_HOVER
            color = settings.COLOR_EDITOR_TEXT
        else:
            fill = settings.COLOR_EDITOR_HEADING
            color = settings.COLOR_EDITOR_TEXT_DIM
        arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, fill)
        arcade.draw_lrbt_rectangle_outline(
            left, right, bottom, top, settings.COLOR_EDITOR_PANEL_BORDER, 1
        )
        self._chip_line(f"chip:{text}:{left:.0f}").draw(
            text,
            left + 8,
            bottom + (top - bottom) * 0.32,
            color,
            max_width=max(8.0, right - left - 14),
            overflow="clip",
        )

    def _draw_grid(
        self,
        current_kind: str,
        counts: dict[str, int],
        hovered: PanelHit | None,
    ) -> None:
        items = palette.items_in(self.tab)
        columns = max(1, settings.EDITOR_GRID_COLUMNS)
        cell_w = (self._width - 16) / columns
        cell_h = float(settings.EDITOR_GRID_CELL_HEIGHT)
        self._clamp_scroll(math.ceil(len(items) / columns) * cell_h + 8)
        top = self._content_top() + self._scroll
        swatch = float(settings.EDITOR_SWATCH_SIZE)
        for index, item in enumerate(items):
            column = index % columns
            row = index // columns
            left = self._left + 8 + column * cell_w
            bottom = top - (row + 1) * cell_h
            cell_top = bottom + cell_h
            if cell_top < self._bottom or bottom > self._content_top():
                continue
            active = item.kind == current_kind
            hovered_item = hovered is not None and hovered.item is item
            if active:
                arcade.draw_lrbt_rectangle_filled(
                    left, left + cell_w - 4, bottom + 2, cell_top - 2, settings.COLOR_EDITOR_ROW_ACTIVE
                )
            elif hovered_item:
                arcade.draw_lrbt_rectangle_filled(
                    left, left + cell_w - 4, bottom + 2, cell_top - 2, settings.COLOR_EDITOR_ROW_HOVER
                )
            arcade.draw_texture_rect(
                icons.cell_texture(item, int(swatch)),
                XYWH(left + 8 + swatch / 2, (bottom + cell_top) / 2, swatch, swatch),
                pixelated=True,
            )
            color = settings.COLOR_EDITOR_TEXT if active else settings.COLOR_EDITOR_TEXT_DIM
            label_x = left + 14 + swatch
            count_w = 22.0
            self._grid_line(item.kind).draw(
                item.label,
                label_x,
                (bottom + cell_top) / 2 - 7,
                color,
                max_width=max(12.0, cell_w - swatch - 24 - count_w),
                overflow="clip",
            )
            total = counts.get(item.kind, 0)
            if total:
                self._count_line(item.kind).draw(
                    str(total),
                    left + cell_w - 10,
                    (bottom + cell_top) / 2 - 7,
                    settings.COLOR_EDITOR_ACCENT,
                )

    def _draw_plates(
        self,
        activators: tuple[Activator, ...],
        selected_index: int | None,
        hovered: PanelHit | None,
        plate_tool: bool,
    ) -> None:
        hints = _plate_hints(bool(activators))
        row_h = float(settings.EDITOR_ROW_HEIGHT)
        hint_h = 22.0
        content = 8 + len(hints) * hint_h + max(1, len(activators)) * row_h
        self._clamp_scroll(content)
        top = self._content_top() + self._scroll - 6
        for hint in hints:
            top -= hint_h
            if top + hint_h < self._bottom or top > self._content_top():
                continue
            self._line(f"hint:{hint}", settings.COLOR_EDITOR_TEXT_DIM).draw(
                hint,
                self._left + 12,
                top + 6,
                settings.COLOR_EDITOR_TEXT_DIM,
                max_width=self._width - 24,
                overflow="clip",
            )
        if not activators:
            return
        for index, activator in enumerate(activators):
            top -= row_h
            bottom = top
            row_top = top + row_h
            if row_top < self._bottom or bottom > self._content_top():
                continue
            active = selected_index == index and plate_tool
            hovered_row = hovered is not None and (
                hovered.activator_index == index
                or hovered.invert_index == index
                or hovered.delete_index == index
            )
            right = self._left + self._width
            if active:
                arcade.draw_lrbt_rectangle_filled(
                    self._left + 2, right, bottom, row_top, settings.COLOR_EDITOR_ROW_ACTIVE
                )
            elif hovered_row:
                arcade.draw_lrbt_rectangle_filled(
                    self._left + 2, right, bottom, row_top, settings.COLOR_EDITOR_ROW_HOVER
                )
            invert_rect, delete_rect = self._plate_controls(bottom, row_top)
            mode = "montre" if activator.inverted else "cache"
            self._draw_chip(
                invert_rect,
                mode,
                hovered=hovered is not None and hovered.invert_index == index,
                active=activator.inverted,
            )
            self._draw_chip(
                delete_rect,
                "x",
                hovered=hovered is not None and hovered.delete_index == index,
                active=False,
            )
            color = settings.COLOR_EDITOR_TEXT if active else settings.COLOR_EDITOR_TEXT_DIM
            label = (
                f"#{index + 1}  {activator.column},{activator.row}  "
                f"x{activator.width}  {len(activator.targets)}"
            )
            self._line(f"plate:{index}", color).draw(
                label,
                self._left + 12,
                bottom + 10,
                color,
                max_width=invert_rect[0] - self._left - 16,
                overflow="clip",
            )

    # ------------------------------------------------------------------ #
    # Hit tests internes
    # ------------------------------------------------------------------ #

    def _hit_grid(self, x: float, y: float) -> PanelHit | None:
        items = palette.items_in(self.tab)
        columns = max(1, settings.EDITOR_GRID_COLUMNS)
        cell_w = (self._width - 16) / columns
        cell_h = float(settings.EDITOR_GRID_CELL_HEIGHT)
        top = self._content_top() + self._scroll
        local_y = top - y
        if local_y < 0:
            return None
        row = int(local_y / cell_h)
        column = int((x - self._left - 8) / cell_w)
        if column < 0 or column >= columns:
            return None
        index = row * columns + column
        if index < 0 or index >= len(items):
            return None
        return PanelHit(item=items[index])

    def _hit_plates(
        self, x: float, y: float, activators: tuple[Activator, ...]
    ) -> PanelHit | None:
        hints = _plate_hints(bool(activators))
        row_h = float(settings.EDITOR_ROW_HEIGHT)
        hint_h = 22.0
        top = self._content_top() + self._scroll - 6 - len(hints) * hint_h
        for index, _activator in enumerate(activators):
            top -= row_h
            bottom = top
            row_top = top + row_h
            if not (bottom <= y <= row_top):
                continue
            invert_rect, delete_rect = self._plate_controls(bottom, row_top)
            if _inside(x, y, *invert_rect):
                return PanelHit(invert_index=index)
            if _inside(x, y, *delete_rect):
                return PanelHit(delete_index=index)
            return PanelHit(activator_index=index)
        return None

    def _plate_controls(
        self, bottom: float, top: float
    ) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
        right = self._left + self._width
        delete = (right - 34, right - 8, bottom + 6, top - 6)
        invert = (right - 118, right - 38, bottom + 6, top - 6)
        return invert, delete

    def _help_rect(self) -> tuple[float, float, float, float]:
        panel_top = self._bottom + self._height
        return (
            self._left + self._width - 78,
            self._left + self._width - 10,
            panel_top - 32,
            panel_top - 8,
        )

    def _theme_rect(self, theme: str) -> tuple[float, float, float, float]:
        ids = theme_ids()
        index = ids.index(theme) if theme in ids else 0
        panel_top = self._bottom + self._height
        top = panel_top - 40
        bottom = top - settings.EDITOR_CHIP_HEIGHT
        gap = 6.0
        usable = self._width - 20
        width = (usable - gap * (len(ids) - 1)) / max(1, len(ids))
        left = self._left + 10 + index * (width + gap)
        return left, left + width, bottom, top

    def _tab_rect(self, tab: str) -> tuple[float, float, float, float]:
        tabs = self.tabs()
        index = tabs.index(tab) if tab in tabs else 0
        panel_top = self._bottom + self._height
        top = panel_top - 40 - settings.EDITOR_CHIP_HEIGHT - 8
        bottom = top - settings.EDITOR_TAB_HEIGHT
        gap = 4.0
        usable = self._width - 16
        width = (usable - gap * (len(tabs) - 1)) / max(1, len(tabs))
        left = self._left + 8 + index * (width + gap)
        return left, left + width, bottom, top

    def _content_top(self) -> float:
        _left, _right, bottom, _top = self._tab_rect(self.tabs()[0])
        return bottom - 8

    def _line(self, key: str, color: tuple[int, int, int]) -> labels.Line:
        text = self._texts.get(key)
        if text is None:
            text = labels.Line(
                settings.EDITOR_GRID_LABEL_SIZE,
                color,
                font_name=settings.EDITOR_UI_FONT,
            )
            self._texts[key] = text
        return text

    def _grid_line(self, key: str) -> labels.Line:
        text = self._small.get(f"grid:{key}")
        if text is None:
            text = labels.Line(
                settings.EDITOR_GRID_LABEL_SIZE,
                settings.COLOR_EDITOR_TEXT_DIM,
                font_name=settings.EDITOR_UI_FONT,
            )
            self._small[f"grid:{key}"] = text
        return text

    def _count_line(self, key: str) -> labels.Line:
        text = self._small.get(f"count:{key}")
        if text is None:
            text = labels.Line(
                settings.EDITOR_GRID_LABEL_SIZE,
                settings.COLOR_EDITOR_ACCENT,
                anchor_x="right",
                font_name=settings.EDITOR_UI_FONT,
            )
            self._small[f"count:{key}"] = text
        return text

    def _chip_line(self, key: str) -> labels.Line:
        text = self._small.get(key)
        if text is None:
            text = labels.Line(
                settings.EDITOR_CHIP_SIZE,
                settings.COLOR_EDITOR_TEXT,
                font_name=settings.EDITOR_UI_FONT,
            )
            self._small[key] = text
        return text

    def _clamp_scroll(self, content: float | None = None) -> None:
        if content is None:
            if self.tab == TAB_PLAQUES:
                content = settings.EDITOR_ROW_HEIGHT * 8
            else:
                count = len(palette.items_in(self.tab))
                columns = max(1, settings.EDITOR_GRID_COLUMNS)
                content = math.ceil(count / columns) * settings.EDITOR_GRID_CELL_HEIGHT
        visible = max(1.0, self._content_top() - self._bottom)
        maximum = max(0.0, content + 8 - visible)
        self._scroll = max(0.0, min(maximum, self._scroll))


def _plate_hints(has_plates: bool) -> tuple[str, ...]:
    if has_plates:
        return (
            "Glisser pour poser. Clic un bloc pour lier.",
            "cache = disparait  |  montre = apparait",
        )
    return (
        "Glisser sur la carte pour poser une plaque.",
        "Puis clic un mur, des piques ou un lance-flammes.",
    )


def _inside(
    x: float,
    y: float,
    left: float,
    right: float,
    bottom: float,
    top: float,
) -> bool:
    return left <= x <= right and bottom <= y <= top
