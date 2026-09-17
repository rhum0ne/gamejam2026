"""Camera et rendu de la grille editee.

Le rendu est volontairement identique au jeu : une cellule est un sprite avec
la texture de la tuile, a `document.tile_size` pixels. Toutes les cellules
vivent dans une seule `SpriteList` (donc un seul appel GPU) mise a jour
cellule par cellule quand le document change : peindre ne reconstruit jamais
la grille entiere, seul un redimensionnement le fait.

Le terrain auto-tile ("wall", cf. `world/obstacles.py`) est recalcule avec la
meme fonction que le jeu (`compute_ground_cells`), sur la carte entiere a
chaque modification, pour que l'apercu dans l'editeur soit exactement ce que
le joueur verra (y compris les coins interieurs, qui peuvent changer
l'apparence d'une case a 2 cases de distance de celle qu'on vient de peindre).

La camera a son propre viewport (la zone hors panneau lateral et barre d'etat)
et son propre `scissor`, pour que le decor ne bave pas sous l'interface.
"""

from __future__ import annotations

import math

import arcade
from arcade.camera import Camera2D
from arcade.types import LBWH, Rect

import settings
from src.editor import icons, palette
from src.editor.activators import Activator, cluster_targets
from src.editor.document import CellState, EditorDocument
from src.editor.selection import Block, GridRect
from src.world.decorations import DECORATION_SPECS, Decoration
from src.world.obstacles import SOLID_GROUND_KINDS, GroundCell, compute_ground_cells, terrain_texture
from src.world.flamethrower import aim_sprite, flame_aabb, flame_start
from src.world.mechanisms import trigger_geometry


class GridCanvas:
    """Vue graphique d'un `EditorDocument` : camera, sprites, reperes."""

    def __init__(self, document: EditorDocument) -> None:
        self.document = document
        self.show_grid = True
        self._viewport: Rect = LBWH(0, 0, settings.EDITOR_WINDOW_WIDTH, settings.EDITOR_WINDOW_HEIGHT)
        self._camera = Camera2D(viewport=self._viewport)
        self._camera.scissor = self._viewport
        self._sprites = arcade.SpriteList()
        self._by_cell: dict[tuple[int, int], arcade.Sprite] = {}
        self._ground_cells: dict[tuple[int, int], GroundCell] = {}
        self._layout_version = document.layout_version
        self.rebuild()
        self._camera.zoom = settings.EDITOR_ZOOM_DEFAULT

    # ------------------------------------------------------------------ #
    # Geometrie
    # ------------------------------------------------------------------ #

    @property
    def viewport(self) -> Rect:
        return self._viewport

    @property
    def zoom(self) -> float:
        return self._camera.zoom

    @property
    def world_width(self) -> float:
        return self.document.columns * self.document.tile_size

    @property
    def world_height(self) -> float:
        return self.document.rows * self.document.tile_size

    def set_viewport(self, left: float, bottom: float, width: float, height: float) -> None:
        """Definit la zone d'ecran dans laquelle la carte est dessinee."""
        self._viewport = LBWH(left, bottom, max(1.0, width), max(1.0, height))
        self._camera.viewport = self._viewport
        self._camera.equalise()
        self._camera.scissor = self._viewport

    def world_from_screen(self, x: float, y: float) -> tuple[float, float]:
        """Coordonnees monde d'un point ecran (sans rotation de camera)."""
        center_x, center_y = self._camera.position
        zoom = self._camera.zoom
        return (
            center_x + (x - self._viewport.center_x) / zoom,
            center_y + (y - self._viewport.center_y) / zoom,
        )

    def grid_from_screen(self, x: float, y: float) -> tuple[int, int]:
        """Cellule (colonne, ligne) sous un point ecran, meme hors de la carte."""
        world_x, world_y = self.world_from_screen(x, y)
        tile = self.document.tile_size
        column = math.floor(world_x / tile)
        row = self.document.rows - 1 - math.floor(world_y / tile)
        return column, row

    def cell_center(self, column: int, row: int) -> tuple[float, float]:
        """Centre monde d'une cellule (ligne 0 = en haut de la carte)."""
        tile = self.document.tile_size
        return (
            column * tile + tile / 2,
            (self.document.rows - 1 - row) * tile + tile / 2,
        )

    def rect_bounds(self, rect: GridRect) -> tuple[float, float, float, float]:
        """Bornes monde (gauche, droite, bas, haut) d'un rectangle de grille."""
        tile = self.document.tile_size
        rows = self.document.rows
        return (
            rect.min_column * tile,
            (rect.max_column + 1) * tile,
            (rows - 1 - rect.max_row) * tile,
            (rows - rect.min_row) * tile,
        )

    def contains_screen(self, x: float, y: float) -> bool:
        """Indique si un point ecran tombe dans la zone de dessin de la carte."""
        return (
            self._viewport.left <= x <= self._viewport.right
            and self._viewport.bottom <= y <= self._viewport.top
        )

    # ------------------------------------------------------------------ #
    # Camera
    # ------------------------------------------------------------------ #

    def pan_by(self, dx: float, dy: float) -> None:
        """Deplace la carte avec la souris : le decor suit le curseur."""
        zoom = self._camera.zoom
        position_x, position_y = self._camera.position
        self._camera.position = (position_x - dx / zoom, position_y - dy / zoom)
        self._clamp_position()

    def nudge(self, dx: float, dy: float) -> None:
        """Deplace la camera dans le sens des touches (Z haut, D droite)."""
        self.pan_by(-dx, -dy)

    def zoom_by(self, factor: float, screen_x: float, screen_y: float) -> None:
        """Zoome en gardant le point ecran donne sur la meme cellule."""
        before = self.world_from_screen(screen_x, screen_y)
        target = self._camera.zoom * factor
        self._camera.zoom = max(settings.EDITOR_ZOOM_MIN, min(settings.EDITOR_ZOOM_MAX, target))
        after = self.world_from_screen(screen_x, screen_y)
        position_x, position_y = self._camera.position
        self._camera.position = (
            position_x + before[0] - after[0],
            position_y + before[1] - after[1],
        )
        self._clamp_position()

    def fit(self) -> None:
        """Cadre la carte entiere dans la zone de dessin (raccourci Origine)."""
        zoom_x = self._viewport.width / max(1.0, self.world_width)
        zoom_y = self._viewport.height / max(1.0, self.world_height)
        zoom = min(zoom_x, zoom_y) * 0.96
        self._camera.zoom = max(settings.EDITOR_ZOOM_MIN, min(settings.EDITOR_ZOOM_MAX, zoom))
        self._camera.position = (self.world_width / 2, self.world_height / 2)

    def focus_spawn(self) -> None:
        """Place la camera sur le depart joueur, au zoom par defaut."""
        self._camera.zoom = settings.EDITOR_ZOOM_DEFAULT
        document = self.document
        for row in range(document.rows):
            for column in range(document.columns):
                if document.cell(column, row) == "player_spawn":
                    self.center_on(column, row)
                    return
        self._camera.position = (self.world_width / 2, self.world_height / 2)
        self._clamp_position()

    def center_on(self, column: int, row: int) -> None:
        self._camera.position = self.cell_center(column, row)
        self._clamp_position()

    # ------------------------------------------------------------------ #
    # Synchronisation avec le document
    # ------------------------------------------------------------------ #

    def sync(self, states: tuple[CellState, ...] | None) -> None:
        """Applique les cellules modifiees, ou reconstruit si la forme a change."""
        if self._layout_version != self.document.layout_version:
            self._layout_version = self.document.layout_version
            self.rebuild()
            return
        if not states:
            return
        changed = {(column, row) for column, row, _ in states}
        previous_ground_cells = self._ground_cells
        self._ground_cells = self._compute_ground_cells()
        for column, row, kind in states:
            self._set_cell(column, row, kind)
        moved = previous_ground_cells.keys() ^ self._ground_cells.keys()
        moved.update(
            key
            for key in previous_ground_cells.keys() & self._ground_cells.keys()
            if previous_ground_cells[key] != self._ground_cells[key]
        )
        for column, row in moved - changed:
            self._set_cell(column, row, self.document.cell(column, row))

    def rebuild(self) -> None:
        """Reconstruit toute la grille (chargement, redimensionnement, undo de forme)."""
        self._sprites.clear()
        self._by_cell.clear()
        self._ground_cells = self._compute_ground_cells()
        document = self.document
        for row in range(document.rows):
            for column in range(document.columns):
                kind = document.cell(column, row)
                if kind:
                    self._set_cell(column, row, kind)
        self._layout_version = document.layout_version

    def _set_cell(self, column: int, row: int, kind: str) -> None:
        existing = self._by_cell.pop((column, row), None)
        if existing is not None:
            existing.remove_from_sprite_lists()
        if not kind:
            return
        item = palette.item(kind)
        center_x, center_y = self.cell_center(column, row)
        if kind in DECORATION_SPECS:
            sprite = Decoration(kind, center_x, center_y)
        elif item.spec is not None and (
            item.spec.sheet is not None or item.spec.role == "ice"
        ):
            texture = terrain_texture(
                item.spec,
                self.document.tile_size,
                cell=self._ground_cells.get((column, row)),
                theme=self.document.theme,
            )
            sprite = arcade.Sprite(texture, center_x=center_x, center_y=center_y)
            if item.spec.tint is not None:
                sprite.color = item.spec.tint
        else:
            texture = icons.cell_texture(item, self.document.tile_size)
            sprite = arcade.Sprite(texture, center_x=center_x, center_y=center_y)
            if item.spec is not None and item.spec.tint is not None:
                sprite.color = item.spec.tint
        if kind == "flamethrower":
            spec = self.document.flame_at(column, row)
            if spec is not None:
                aim_sprite(sprite, spec.direction)
        if kind == settings.TILE_KIND_FALLING:
            falling = self.document.falling_at(column, row)
            if falling is not None and falling.ghost_only:
                sprite.color = settings.COLOR_FALLING_BLOCK_GHOST
                sprite.alpha = settings.FALLING_BLOCK_GHOST_ALPHA
        self._sprites.append(sprite)
        self._by_cell[(column, row)] = sprite

    def _compute_ground_cells(self) -> dict[tuple[int, int], GroundCell]:
        """Resout la case `SHEET_GROUND` de toute la grille (cf. `obstacles.compute_ground_cells`).

        Recalculee sur toute la carte a chaque modification (pas seulement les
        4 voisines directes) : les coins interieurs regardent jusqu'a 2 cases
        plus loin (la voisine de leur propre voisine), donc une seule tuile
        modifiee peut changer l'apparence de cases non adjacentes.
        """
        document = self.document

        def is_solid(column: int, row: int) -> bool:
            # Hors carte = solide, comme en jeu (`level._compute_ground_cells`) :
            # pas d'herbe ni de pilier sur les tuiles de bordure.
            if not document.inside(column, row):
                return True
            return document.cell(column, row) in SOLID_GROUND_KINDS

        def is_autotile(column: int, row: int) -> bool:
            kind = document.cell(column, row)
            if not kind:
                return False
            spec = palette.item(kind).spec
            return spec is not None and spec.autotile

        return compute_ground_cells(
            document.columns, document.rows, is_solid=is_solid, is_autotile=is_autotile
        )

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #

    def draw(
        self,
        *,
        selection: GridRect | None = None,
        hover: tuple[int, int] | None = None,
        preview: GridRect | None = None,
        clipboard: Block | None = None,
        activators: tuple[Activator, ...] = (),
        selected_activator: int | None = None,
        preview_plate: Activator | None = None,
    ) -> None:
        """Dessine le fond de carte, les cellules, la grille et les reperes."""
        self._camera.use()
        arcade.draw_lrbt_rectangle_filled(
            0, self.world_width, 0, self.world_height, settings.COLOR_BACKGROUND
        )
        self._sprites.draw(pixelated=True)
        self._draw_ghost_falling_outlines()
        if self.show_grid and self._camera.zoom >= settings.EDITOR_GRID_MIN_ZOOM:
            self._draw_grid()
        arcade.draw_lrbt_rectangle_outline(
            0, self.world_width, 0, self.world_height, settings.COLOR_EDITOR_BOUNDS, 2
        )
        self._draw_activators(activators, selected_activator, preview_plate)
        if selection is not None:
            self._draw_rect(selection, settings.COLOR_EDITOR_SELECTION, settings.COLOR_EDITOR_SELECTION_BORDER)
        if preview is not None:
            self._draw_rect(preview, settings.COLOR_EDITOR_PASTE, settings.COLOR_EDITOR_WARNING)
        if hover is not None and self.document.inside(*hover):
            cell = GridRect(hover[0], hover[1], hover[0], hover[1])
            self._draw_rect(cell, settings.COLOR_EDITOR_HOVER, settings.COLOR_EDITOR_ACCENT)
            self._draw_flame_preview(*hover)
        if clipboard is not None and hover is not None:
            self._draw_rect(
                clipboard.rect_at(*hover), settings.COLOR_EDITOR_PASTE, settings.COLOR_EDITOR_WARNING
            )

    def _draw_activators(
        self,
        activators: tuple[Activator, ...],
        selected_index: int | None,
        preview: Activator | None,
    ) -> None:
        drawn = list(activators)
        if preview is not None:
            drawn.append(preview)
        for index, activator in enumerate(drawn):
            selected = index == selected_index or activator is preview
            self._draw_plate(activator, selected)
            self._draw_links(activator, selected)

    def _draw_plate(self, activator: Activator, selected: bool) -> None:
        if activator.is_spectral:
            fill = settings.COLOR_EDITOR_PLATE_SELECTED if selected else settings.COLOR_EDITOR_SPECTRAL
            border = (
                settings.COLOR_EDITOR_WARNING if selected else settings.COLOR_EDITOR_SPECTRAL_BORDER
            )
            lamp = (
                settings.COLOR_SPECTRAL_BUTTON_ACTIVE
                if selected
                else settings.COLOR_SPECTRAL_BUTTON
            )
        else:
            fill = settings.COLOR_EDITOR_PLATE_SELECTED if selected else settings.COLOR_EDITOR_PLATE
            border = (
                settings.COLOR_EDITOR_WARNING if selected else settings.COLOR_EDITOR_PLATE_BORDER
            )
            lamp = (
                settings.COLOR_PRESSURE_PLATE_PRESSED if selected else settings.COLOR_PRESSURE_PLATE
            )
        rect = GridRect(
            activator.column,
            activator.row,
            activator.last_column,
            activator.row,
        )
        self._draw_rect(rect, fill, border)
        center_x, center_y, width, height = trigger_geometry(
            activator.column,
            activator.row,
            activator.width,
            self.document.tile_size,
            self.document.rows,
            activator.kind,
        )
        arcade.draw_lrbt_rectangle_filled(
            center_x - width / 2,
            center_x + width / 2,
            center_y - height / 2,
            center_y + height / 2,
            lamp,
        )

    def _draw_links(self, activator: Activator, selected: bool) -> None:
        if not activator.targets:
            return
        tile = self.document.tile_size
        start_x, start_y, _width, _height = trigger_geometry(
            activator.column,
            activator.row,
            activator.width,
            tile,
            self.document.rows,
            activator.kind,
        )
        for target in activator.targets:
            fill, border, _link = _action_style(target.action, selected)
            self._draw_rect(
                GridRect(target.column, target.row, target.column, target.row),
                fill,
                border,
            )
        for center_column, center_row, action in cluster_targets(activator.targets):
            _fill, _border, color = _action_style(action, selected)
            target_x = center_column * tile + tile / 2
            target_y = (self.document.rows - 1 - center_row) * tile + tile / 2
            arcade.draw_line(start_x, start_y, target_x, target_y, color, 2)

    def _draw_ghost_falling_outlines(self) -> None:
        """Repere cyan sur les blocs tombants visibles seulement au fantome."""
        color = settings.COLOR_FALLING_BLOCK_GHOST
        for spec in self.document.falling_specs():
            if not spec.ghost_only:
                continue
            left, right, bottom, top = self.rect_bounds(
                GridRect(spec.column, spec.row, spec.column, spec.row)
            )
            arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, color, 2)

    def _draw_flame_preview(self, column: int, row: int) -> None:
        """Montre la portee du lance-flammes sous le curseur."""
        spec = self.document.flame_at(column, row)
        if spec is None:
            return
        tile = self.document.tile_size
        center_x, center_y = self.cell_center(column, row)
        origin_x, origin_y = flame_start(center_x, center_y, spec.direction, tile)
        left, right, bottom, top = flame_aabb(
            origin_x,
            origin_y,
            spec.direction,
            spec.range_tiles * tile,
            settings.FLAMETHROWER_HEIGHT,
        )
        arcade.draw_lrbt_rectangle_filled(
            left, right, bottom, top, settings.COLOR_FLAME_PREVIEW
        )
        arcade.draw_lrbt_rectangle_outline(
            left, right, bottom, top, settings.COLOR_FLAMETHROWER, 1
        )

    def _draw_rect(
        self,
        rect: GridRect,
        fill: tuple[int, int, int, int],
        border: tuple[int, int, int],
    ) -> None:
        left, right, bottom, top = self.rect_bounds(rect)
        arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, fill)
        arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, border, 2)

    def _draw_grid(self) -> None:
        """Trace uniquement les lignes visibles a l'ecran."""
        tile = self.document.tile_size
        left, bottom = self.world_from_screen(self._viewport.left, self._viewport.bottom)
        right, top = self.world_from_screen(self._viewport.right, self._viewport.top)
        first_column = max(0, math.floor(left / tile))
        last_column = min(self.document.columns, math.ceil(right / tile))
        first_row = max(0, math.floor(bottom / tile))
        last_row = min(self.document.rows, math.ceil(top / tile))
        color = settings.COLOR_EDITOR_GRID
        for column in range(first_column, last_column + 1):
            x = column * tile
            arcade.draw_line(x, first_row * tile, x, last_row * tile, color, 1)
        for row in range(first_row, last_row + 1):
            y = row * tile
            arcade.draw_line(first_column * tile, y, last_column * tile, y, color, 1)

    def _clamp_position(self) -> None:
        """Garde la carte a portee : on ne peut pas se perdre dans le vide."""
        margin_x = self._viewport.width / self._camera.zoom
        margin_y = self._viewport.height / self._camera.zoom
        position_x, position_y = self._camera.position
        self._camera.position = (
            max(-margin_x, min(self.world_width + margin_x, position_x)),
            max(-margin_y, min(self.world_height + margin_y, position_y)),
        )


def _action_style(
    action: str, selected: bool
) -> tuple[tuple[int, int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    """Couleurs (fill, border, lien) d'une cible selon son action."""
    if action == settings.LINK_ACTION_SHOW:
        fill = settings.COLOR_EDITOR_GATED_INVERT
        border = settings.COLOR_EDITOR_GATED_INVERT_BORDER
        link = settings.COLOR_EDITOR_WARNING if selected else settings.COLOR_EDITOR_LINK_INVERT
    elif action == settings.LINK_ACTION_IGNITE:
        fill = settings.COLOR_EDITOR_GATED_IGNITE
        border = settings.COLOR_EDITOR_GATED_IGNITE_BORDER
        link = settings.COLOR_EDITOR_WARNING if selected else settings.COLOR_EDITOR_LINK_IGNITE
    else:
        fill = settings.COLOR_EDITOR_GATED
        border = settings.COLOR_EDITOR_GATED_BORDER
        link = settings.COLOR_EDITOR_WARNING if selected else settings.COLOR_EDITOR_LINK
    return fill, border, link
