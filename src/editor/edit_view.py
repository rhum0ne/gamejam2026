"""Vue d'edition : pinceau, selection, collage, historique, raccourcis.

Les outils sont volontairement peu nombreux et stables. Ajouter un type de
tuile ne passe pas par ici : il apparait tout seul dans `palette.PALETTE`.
"""

from __future__ import annotations

from enum import Enum

import arcade

import settings
from src.editor import palette
from src.editor.activators import Activator, activator_at, overlaps_any
from src.editor.canvas import GridCanvas
from src.editor.document import DocumentError, EditorDocument
from src.editor.overlay import HelpOverlay, StatusBar, StatusData, TextPrompt
from src.editor.panel import PalettePanel
from src.editor.selection import Block, GridRect
from src.ui.display import handle_display_key, use_default_camera
from src.world.flamethrower import DIRECTION_ARROW, DIRECTION_LABEL

# 9/0 : rangee du haut (KEY_*) et pave (NUM_*). CCEDILLA/AGRAVE = 9/0 AZERTY sans Shift.
_FLAME_INTERVAL_SHORTER = frozenset(
    {arcade.key.KEY_9, arcade.key.NUM_9, getattr(arcade.key, "CCEDILLA", 231)}
)
_FLAME_INTERVAL_LONGER = frozenset(
    {arcade.key.KEY_0, arcade.key.NUM_0, getattr(arcade.key, "AGRAVE", 224)}
)


class Tool(Enum):
    """Outil actif. La valeur est le libelle affiche dans la barre d'etat."""

    BRUSH = "pinceau"
    RECT = "rectangle"
    FILL = "zone"
    ERASE = "gomme"
    PICK = "pipette"
    SELECT = "selection"
    LINK = "plaques"


_CTRL = arcade.key.MOD_CTRL | arcade.key.MOD_ACCEL
_SHIFT = arcade.key.MOD_SHIFT


def _held(modifiers: int, mask: int) -> bool:
    return bool(modifiers & mask)


def _line_cells(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Cellules d'un segment (Bresenham) pour ne pas sauter de cases en glissant."""
    column, row = start
    target_column, target_row = end
    delta_column = abs(target_column - column)
    delta_row = abs(target_row - row)
    step_column = 1 if column < target_column else -1
    step_row = 1 if row < target_row else -1
    error = delta_column - delta_row
    cells: list[tuple[int, int]] = []
    while True:
        cells.append((column, row))
        if column == target_column and row == target_row:
            return cells
        doubled = 2 * error
        if doubled > -delta_row:
            error -= delta_row
            column += step_column
        if doubled < delta_column:
            error += delta_column
            row += step_row


class EditView(arcade.View):
    """Edite une carte : dessin a gauche, palette a droite, statut en bas."""

    def __init__(self, document: EditorDocument) -> None:
        super().__init__()
        self.background_color = settings.COLOR_EDITOR_BACKGROUND
        self.document = document
        self.canvas = GridCanvas(document)
        self.panel = PalettePanel()
        self.status = StatusBar()
        self.help = HelpOverlay()
        self.prompt = TextPrompt()
        self.tool = Tool.BRUSH
        self.kind = "wall"
        self.selection: GridRect | None = None
        self.clipboard: Block | None = None
        self.hover: tuple[int, int] | None = None
        self._mouse = (0.0, 0.0)
        self._drag_origin: tuple[int, int] | None = None
        self._drag_current: tuple[int, int] | None = None
        self._painting = False
        self._erasing = False
        self._panning = False
        self._space = False
        self._held: set[int] = set()
        self._link_index: int | None = None
        self._placing_plate = False
        self._resizing_plate = False
        self._message = ""
        self._message_time = 0.0
        self._message_color = settings.COLOR_EDITOR_OK
        self._camera_ready = False

    # ------------------------------------------------------------------ #
    # Cycle de vie
    # ------------------------------------------------------------------ #

    def on_show_view(self) -> None:
        use_default_camera(self.window)
        self._layout()
        if not self._camera_ready:
            self.canvas.focus_spawn()
            self._camera_ready = True

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        self._layout()

    def _layout(self) -> None:
        width = float(self.window.width)
        height = float(self.window.height)
        self.panel.layout(width, height)
        self.canvas.set_viewport(
            0.0,
            float(settings.EDITOR_STATUS_HEIGHT),
            max(1.0, width - self.panel.width),
            max(1.0, height - settings.EDITOR_STATUS_HEIGHT),
        )

    # ------------------------------------------------------------------ #
    # Dessin / tick
    # ------------------------------------------------------------------ #

    def on_draw(self) -> None:
        self.clear()
        preview = None
        if self.tool is Tool.RECT and self._drag_origin is not None and self._drag_current is not None:
            preview = GridRect.from_corners(self._drag_origin, self._drag_current)
        selection = self.selection
        if self.tool is Tool.SELECT and self._drag_origin is not None and self._drag_current is not None:
            selection = GridRect.from_corners(self._drag_origin, self._drag_current)
        paste = self.clipboard if self.tool is not Tool.SELECT else None
        preview_plate = None
        if self.tool is Tool.LINK and self._placing_plate and self._drag_origin and self._drag_current:
            preview_plate = _plate_from_drag(self._drag_origin, self._drag_current)
        self.canvas.draw(
            selection=selection,
            hover=self.hover,
            preview=preview,
            clipboard=paste if self.clipboard is not None and self.hover is not None else None,
            activators=self.document.activators,
            selected_activator=self._link_index,
            preview_plate=preview_plate,
        )
        use_default_camera(self.window)
        self.window.ctx.scissor = None
        self.window.ctx.viewport = (0, 0, self.window.width, self.window.height)
        self.panel.draw(
            self.kind,
            self.document.counts(),
            *self._mouse,
            self.document.activators,
            self._link_index,
            self.tool is Tool.LINK,
        )
        self.status.draw(self._status_data(), float(self.window.width))
        self.help.draw(float(self.window.width), float(self.window.height))
        self.prompt.draw(float(self.window.width), float(self.window.height))

    def on_update(self, delta_time: float) -> None:
        if self._message_time > 0.0:
            self._message_time = max(0.0, self._message_time - delta_time)
            if self._message_time == 0.0:
                self._message = ""
        if self.prompt.active or self.help.visible:
            return
        speed = settings.EDITOR_PAN_SPEED * delta_time
        dx = dy = 0.0
        if self._held & {arcade.key.LEFT, arcade.key.A, arcade.key.Q}:
            dx -= speed
        if self._held & {arcade.key.RIGHT, arcade.key.D}:
            dx += speed
        if self._held & {arcade.key.DOWN, arcade.key.S}:
            dy -= speed
        if self._held & {arcade.key.UP, arcade.key.W, arcade.key.Z}:
            dy += speed
        if dx or dy:
            self.canvas.nudge(dx, dy)

    def _status_data(self) -> StatusData:
        selection = "-"
        if self.selection is not None:
            selection = f"{self.selection.width}x{self.selection.height}"
        clipboard = "-"
        if self.clipboard is not None:
            clipboard = f"{self.clipboard.width}x{self.clipboard.height}"
        element = palette.item(self.kind).label if self.kind else "vide"
        if self.hover is not None and self.document.inside(*self.hover):
            flame = self.document.flame_at(*self.hover)
            if flame is not None:
                arrow = DIRECTION_ARROW[flame.direction]
                element = (
                    f"Lance-flammes {arrow} portee {flame.range_tiles} "
                    f"int {flame.interval:.1f}s"
                )
            falling = self.document.falling_at(*self.hover)
            if falling is not None:
                element = (
                    f"Bloc tombant delay {falling.delay:.2f}s "
                    f"respawn {falling.respawn:.1f}s"
                )
        plates = f"{len(self.document.activators)}"
        if self._link_index is not None and 0 <= self._link_index < len(self.document.activators):
            chosen = self.document.activators[self._link_index]
            plates = (
                f"#{self._link_index + 1} {chosen.column},{chosen.row} "
                f"x{chosen.width} -> {len(chosen.targets)}"
                f"{'  montre' if chosen.inverted else '  cache'}"
            )
        message = self._message if self._message_time > 0.0 else ""
        return StatusData(
            filename=self.document.filename,
            name=self.document.name,
            dirty=self.document.dirty,
            columns=self.document.columns,
            rows=self.document.rows,
            zoom=self.canvas.zoom,
            tool=self.tool.value,
            element=element,
            hover=self.hover if self.hover is not None and self.document.inside(*self.hover) else None,
            selection=selection,
            clipboard=clipboard,
            undo_label=self.document.history.undo_label,
            redo_label=self.document.history.redo_label,
            message=message,
            message_color=self._message_color,
            problems=self.document.problems(),
            plates=plates,
        )

    def notify(self, text: str, color: tuple[int, int, int] = settings.COLOR_EDITOR_OK) -> None:
        """Affiche un message temporaire dans la barre d'etat."""
        self._message = text
        self._message_color = color
        self._message_time = settings.EDITOR_MESSAGE_TIME

    # ------------------------------------------------------------------ #
    # Souris
    # ------------------------------------------------------------------ #

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        self._mouse = (x, y)
        if self._panning:
            self.canvas.pan_by(dx, dy)
            return
        if self.canvas.contains_screen(x, y):
            self.hover = self.canvas.grid_from_screen(x, y)
        if self._painting or self._erasing:
            self._stroke_to(self.hover)
        elif self._drag_origin is not None and self.hover is not None:
            self._drag_current = self.hover

    def on_mouse_drag(
        self, x: float, y: float, dx: float, dy: float, buttons: int, modifiers: int
    ) -> None:
        self.on_mouse_motion(x, y, dx, dy)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        if self.prompt.active or self.help.visible:
            return
        self._mouse = (x, y)
        if button == arcade.MOUSE_BUTTON_MIDDLE or self._space:
            self._panning = True
            return
        if self.panel.contains(x, y):
            self._panel_click(x, y, button)
            return
        if not self.canvas.contains_screen(x, y):
            return
        cell = self.canvas.grid_from_screen(x, y)
        self.hover = cell
        if self.tool is Tool.LINK:
            self._link_press(cell, button)
            return
        if button == arcade.MOUSE_BUTTON_RIGHT:
            self._erasing = True
            self.document.begin_stroke("effacer")
            self._stroke_to(cell)
            return
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        if self.tool is Tool.PICK:
            self._pick(cell)
            return
        if self.tool is Tool.FILL:
            kind = self.kind
            self._apply(self.document.fill_area(*cell, kind), "zone remplie")
            return
        if self.tool in (Tool.RECT, Tool.SELECT):
            self._drag_origin = cell
            self._drag_current = cell
            return
        self._painting = True
        self._drag_current = None
        label = "effacer" if self.tool is Tool.ERASE else "peindre"
        self.document.begin_stroke(label)
        self._stroke_to(cell)

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int) -> None:
        if button == arcade.MOUSE_BUTTON_MIDDLE:
            self._panning = False
        if button == arcade.MOUSE_BUTTON_RIGHT:
            self._finish_stroke()
            self._erasing = False
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        self._panning = False
        if self._painting:
            self._finish_stroke()
            self._painting = False
        if self.tool is Tool.LINK and (self._placing_plate or self._resizing_plate):
            self._finish_plate_drag()
            return
        if self._drag_origin is not None and self._drag_current is not None:
            rect = GridRect.from_corners(self._drag_origin, self._drag_current)
            if self.tool is Tool.RECT:
                self._apply(self.document.fill_rect(rect, self.kind))
            elif self.tool is Tool.SELECT:
                self.selection = rect.clamped(self.document.columns, self.document.rows)
            self._drag_origin = None
            self._drag_current = None

    def on_mouse_scroll(self, x: float, y: float, scroll_x: float, scroll_y: float) -> None:
        if self.prompt.active:
            return
        # Molette et trackpad etaient inverses par rapport a ZQSD / au zoom attendu.
        scroll_y = -scroll_y
        if self.panel.contains(x, y):
            self.panel.scroll_by(-scroll_y)
            return
        if self.canvas.contains_screen(x, y) and scroll_y:
            factor = settings.EDITOR_ZOOM_STEP if scroll_y > 0 else 1.0 / settings.EDITOR_ZOOM_STEP
            self.canvas.zoom_by(factor, x, y)

    def _stroke_to(self, cell: tuple[int, int] | None) -> None:
        if cell is None:
            return
        kind = palette.EMPTY if self._erasing or self.tool is Tool.ERASE else self.kind
        origin = self._drag_current if self._drag_current is not None else cell
        self._apply(self.document.paint(_line_cells(origin, cell), kind), silent=True)
        self._drag_current = cell

    def _finish_stroke(self) -> None:
        self.document.end_stroke()
        self._drag_current = None

    def _pick(self, cell: tuple[int, int]) -> None:
        kind = self.document.cell(*cell)
        if not kind:
            self.tool = Tool.ERASE
            self.notify("pipette : vide (gomme)")
            return
        self._select_kind(kind)
        self.tool = Tool.BRUSH
        self.notify(f"pipette : {palette.item(kind).label}")

    def _select_kind(self, kind: str) -> None:
        self.kind = kind
        if self.tool in (Tool.ERASE, Tool.LINK):
            self.tool = Tool.BRUSH

    # ------------------------------------------------------------------ #
    # Clavier
    # ------------------------------------------------------------------ #

    def on_text(self, text: str) -> None:
        self.prompt.on_text(text)

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        self._held.discard(symbol)
        if symbol == arcade.key.SPACE:
            self._space = False
            self._panning = False

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if self.prompt.on_key_press(symbol, modifiers):
            return
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.F1:
            self.help.toggle()
            return
        if self.help.visible:
            if symbol == arcade.key.ESCAPE:
                self.help.visible = False
            return
        ctrl = _held(modifiers, _CTRL)
        shift = _held(modifiers, _SHIFT)
        if not ctrl:
            self._held.add(symbol)
        if symbol == arcade.key.SPACE:
            self._space = True
            return
        if ctrl and symbol == arcade.key.Z:
            self._redo() if shift else self._undo()
            return
        if ctrl and symbol == arcade.key.Y:
            self._redo()
            return
        if ctrl and symbol == arcade.key.S:
            self._save_as() if shift else self._save()
            return
        if ctrl and symbol == arcade.key.C:
            self._copy(cut=False)
            return
        if ctrl and symbol == arcade.key.X:
            self._copy(cut=True)
            return
        if ctrl and symbol == arcade.key.V:
            self._paste()
            return
        if ctrl and symbol == arcade.key.A:
            self.selection = GridRect.whole(self.document.columns, self.document.rows)
            self.tool = Tool.SELECT
            self.notify("tout selectionne")
            return
        if ctrl and symbol == arcade.key.R:
            self._replace_under_cursor()
            return
        if ctrl and symbol == arcade.key.G:
            self.canvas.show_grid = not self.canvas.show_grid
            return
        if ctrl and symbol == arcade.key.P:
            self._playtest()
            return
        if ctrl and symbol == arcade.key.O:
            self._leave()
            return
        if symbol in (arcade.key.DELETE, arcade.key.BACKSPACE):
            self._delete_selection()
            return
        if symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER):
            self._fill_selection()
            return
        if symbol == arcade.key.HOME:
            self.canvas.fit()
            return
        if symbol == arcade.key.ESCAPE:
            self._leave()
            return
        if symbol == arcade.key.F2:
            self._ask_name()
            return
        if symbol == arcade.key.F3:
            self._ask_hint()
            return
        if symbol == arcade.key.F4:
            self._ask_size()
            return
        if symbol == arcade.key.BRACKETLEFT:
            self._cycle_kind(-1)
            return
        if symbol == arcade.key.BRACKETRIGHT:
            self._cycle_kind(1)
            return
        if self._tune_flamethrower(symbol):
            return
        if self._tune_falling_block(symbol):
            return
        if self._tune_activator(symbol):
            return
        if symbol in (arcade.key.EQUAL, arcade.key.PLUS, arcade.key.NUM_ADD):
            self.canvas.zoom_by(settings.EDITOR_ZOOM_STEP, *self._mouse)
            return
        if symbol in (arcade.key.MINUS, arcade.key.NUM_SUBTRACT):
            self.canvas.zoom_by(1.0 / settings.EDITOR_ZOOM_STEP, *self._mouse)
            return
        self._tool_hotkey(symbol)

    def _tool_hotkey(self, symbol: int) -> None:
        mapping = {
            arcade.key.B: Tool.BRUSH,
            arcade.key.R: Tool.RECT,
            arcade.key.G: Tool.FILL,
            arcade.key.X: Tool.ERASE,
            arcade.key.I: Tool.PICK,
            arcade.key.M: Tool.SELECT,
            arcade.key.L: Tool.LINK,
        }
        tool = mapping.get(symbol)
        if tool is not None:
            self.tool = tool
            if tool is Tool.LINK:
                self.notify(
                    "plaques : glisser pour placer, clic sur un bloc pour lier, "
                    "V pour inverser, Suppr pour retirer"
                )
            else:
                self.notify(f"outil : {tool.value}")

    def _cycle_kind(self, step: int) -> None:
        kinds = [item.kind for item in palette.PALETTE]
        if self.kind not in kinds:
            self.kind = kinds[0]
            return
        index = (kinds.index(self.kind) + step) % len(kinds)
        self._select_kind(kinds[index])

    def _tune_flamethrower(self, symbol: int) -> bool:
        """Regle portee / intervalle / orientation du lance-flammes sous le curseur."""
        if self.hover is None or not self.document.inside(*self.hover):
            return False
        if self.document.cell(*self.hover) != "flamethrower":
            return False
        range_delta = 0
        interval_delta = 0.0
        rotate = False
        if symbol == arcade.key.PERIOD:
            range_delta = 1
        elif symbol == arcade.key.COMMA:
            range_delta = -1
        elif symbol in _FLAME_INTERVAL_LONGER:
            interval_delta = settings.FLAMETHROWER_INTERVAL_STEP
        elif symbol in _FLAME_INTERVAL_SHORTER:
            interval_delta = -settings.FLAMETHROWER_INTERVAL_STEP
        elif symbol == arcade.key.H:
            rotate = True
        else:
            return False
        spec = self.document.adjust_flame(
            *self.hover,
            range_delta=range_delta,
            interval_delta=interval_delta,
            rotate=rotate,
        )
        if spec is None:
            return True
        self.canvas.sync(((*self.hover, "flamethrower"),))
        facing = DIRECTION_LABEL[spec.direction]
        self.notify(
            f"lance-flammes : portee {spec.range_tiles}  "
            f"intervalle {spec.interval:.1f}s  {facing}"
        )
        return True

    def _tune_falling_block(self, symbol: int) -> bool:
        """Regle delay / respawn du bloc tombant sous le curseur."""
        if self.hover is None or not self.document.inside(*self.hover):
            return False
        if self.document.cell(*self.hover) != settings.TILE_KIND_FALLING:
            return False
        delay_delta = 0.0
        respawn_delta = 0.0
        if symbol == arcade.key.PERIOD:
            delay_delta = settings.FALLING_BLOCK_DELAY_STEP
        elif symbol == arcade.key.COMMA:
            delay_delta = -settings.FALLING_BLOCK_DELAY_STEP
        elif symbol in _FLAME_INTERVAL_LONGER:
            respawn_delta = settings.FALLING_BLOCK_RESPAWN_STEP
        elif symbol in _FLAME_INTERVAL_SHORTER:
            respawn_delta = -settings.FALLING_BLOCK_RESPAWN_STEP
        else:
            return False
        spec = self.document.adjust_falling(
            *self.hover,
            delay_delta=delay_delta,
            respawn_delta=respawn_delta,
        )
        if spec is None:
            return True
        self.canvas.sync(((*self.hover, settings.TILE_KIND_FALLING),))
        self.notify(
            f"bloc tombant : delay {spec.delay:.2f}s  respawn {spec.respawn:.1f}s"
        )
        return True

    def _tune_activator(self, symbol: int) -> bool:
        """Inverse cache / montre de la plaque selectionnee ou sous le curseur."""
        if symbol != arcade.key.V:
            return False
        index = self._link_index
        if index is None and self.hover is not None and self.document.inside(*self.hover):
            index = activator_at(self.document.activators, *self.hover)
        if index is None:
            return False
        inverted = self.document.toggle_activator_invert(index)
        self._link_index = index
        mode = "montre a l'activation" if inverted else "cache a l'activation"
        self.notify(f"plaque #{index + 1} : {mode}")
        return True

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def _apply(self, states, message: str | None = None, *, silent: bool = False) -> None:
        self.canvas.sync(states)
        self._clamp_link_index()
        if message and states:
            self.notify(message)
        elif not silent and not states and message:
            self.notify("aucun changement", settings.COLOR_EDITOR_TEXT_DIM)

    def _undo(self) -> None:
        states = self.document.undo()
        if states is None:
            self.notify("rien a annuler", settings.COLOR_EDITOR_TEXT_DIM)
            return
        self.canvas.sync(states)
        self._clamp_link_index()
        self.notify(f"annule : {self.document.history.redo_label}")

    def _redo(self) -> None:
        states = self.document.redo()
        if states is None:
            self.notify("rien a refaire", settings.COLOR_EDITOR_TEXT_DIM)
            return
        self.canvas.sync(states)
        self._clamp_link_index()
        self.notify(f"refait : {self.document.history.undo_label}")

    def _copy(self, *, cut: bool) -> None:
        if self.selection is None:
            self.notify("pas de selection", settings.COLOR_EDITOR_WARNING)
            return
        block = self.document.block(self.selection)
        if block is None:
            return
        self.clipboard = block
        if cut:
            self._apply(self.document.fill_rect(self.selection, palette.EMPTY), "coupe")
            self.selection = None
        else:
            self.notify(f"copie {block.width}x{block.height}")

    def _paste(self) -> None:
        if self.clipboard is None:
            self.notify("presse-papiers vide", settings.COLOR_EDITOR_WARNING)
            return
        origin = self.hover
        if origin is None or not self.document.inside(*origin):
            origin = (0, 0)
        self._apply(self.document.stamp(*origin, self.clipboard), "colle")
        self.selection = self.clipboard.rect_at(*origin).clamped(
            self.document.columns, self.document.rows
        )

    def _delete_selection(self) -> None:
        if self.tool is Tool.LINK and self._link_index is not None:
            self._delete_plate(self._link_index)
            return
        if self.selection is None:
            if self.hover is not None:
                self._apply(self.document.paint((self.hover,), palette.EMPTY), "cellule effacee")
            return
        self._apply(self.document.fill_rect(self.selection, palette.EMPTY), "selection videe")

    def _fill_selection(self) -> None:
        if self.selection is None:
            self.notify("pas de selection", settings.COLOR_EDITOR_WARNING)
            return
        self._apply(self.document.fill_rect(self.selection, self.kind), "selection remplie")

    def _replace_under_cursor(self) -> None:
        if self.hover is None or not self.document.inside(*self.hover):
            self.notify("aucune cellule sous le curseur", settings.COLOR_EDITOR_WARNING)
            return
        old_kind = self.document.cell(*self.hover)
        self._apply(
            self.document.replace_kind(old_kind, self.kind, self.selection),
            "type remplace",
        )

    def _save(self) -> None:
        if self.document.path is None:
            self._save_as()
            return
        try:
            path = self.document.save()
        except DocumentError as error:
            self.notify(str(error), settings.COLOR_EDITOR_DANGER)
            return
        self.notify(f"enregistre : {path.name}")

    def _save_as(self) -> None:
        suggestion = self.document.path.stem if self.document.path else _slug(self.document.name)
        self.prompt.ask("Enregistrer sous (nom de fichier, sans .json)", suggestion, self._on_save_as)

    def _on_save_as(self, value: str) -> None:
        name = _slug(value)
        if not name:
            self.notify("nom vide", settings.COLOR_EDITOR_DANGER)
            return
        try:
            path = self.document.save(name)
        except DocumentError as error:
            self.notify(str(error), settings.COLOR_EDITOR_DANGER)
            return
        self.notify(f"enregistre : {path.name}")

    def _ask_name(self) -> None:
        self.prompt.ask("Nom du niveau", self.document.name, self._on_name)

    def _on_name(self, value: str) -> None:
        name = value.strip() or self.document.name
        self.document.set_metadata(name=name)
        self.notify(f"nom : {name}")

    def _ask_hint(self) -> None:
        self.prompt.ask("Indice affiche dans le HUD", self.document.hint, self._on_hint)

    def _on_hint(self, value: str) -> None:
        self.document.set_metadata(hint=value)
        self.notify("indice mis a jour")

    def _ask_size(self) -> None:
        current = f"{self.document.columns}x{self.document.rows}"
        self.prompt.ask("Dimensions (colonnes x lignes)", current, self._on_size)

    def _on_size(self, value: str) -> None:
        cleaned = value.lower().replace(" ", "")
        if "x" not in cleaned:
            self.notify("format attendu : 80x40", settings.COLOR_EDITOR_DANGER)
            return
        left, right = cleaned.split("x", 1)
        try:
            columns = int(left)
            rows = int(right)
        except ValueError:
            self.notify("nombres invalides", settings.COLOR_EDITOR_DANGER)
            return
        if self.document.resize(columns, rows):
            self.canvas.sync(None)
            self.canvas.fit()
            self.selection = None
            self.notify(f"taille : {self.document.columns}x{self.document.rows}")
        else:
            self.notify("taille inchangee", settings.COLOR_EDITOR_TEXT_DIM)

    def _playtest(self) -> None:
        from src.editor.playtest import start_playtest

        if self.document.path is None or self.document.dirty:
            try:
                if self.document.path is None:
                    self._save_as()
                    self.notify("enregistre la carte, puis Ctrl+P", settings.COLOR_EDITOR_WARNING)
                    return
                self.document.save()
            except DocumentError as error:
                self.notify(str(error), settings.COLOR_EDITOR_DANGER)
                return
        start_playtest(self.window, self.document, self._resume)

    def _resume(self) -> None:
        self.window.show_view(self)

    def _leave(self) -> None:
        if self.document.dirty:
            self.prompt.confirm(
                "Modifications non enregistrees. Quitter quand meme ?",
                lambda _value: self._open_browser(),
            )
            return
        self._open_browser()

    def _open_browser(self) -> None:
        from src.editor.browser import BrowserView

        self.window.show_view(BrowserView())

    # ------------------------------------------------------------------ #
    # Plaques et blocs lies
    # ------------------------------------------------------------------ #

    def _panel_click(self, x: float, y: float, button: int) -> None:
        hit = self.panel.hit(x, y, self.document.activators)
        if hit is None:
            return
        if hit.activator_index is not None:
            if button == arcade.MOUSE_BUTTON_RIGHT:
                self._delete_plate(hit.activator_index)
                return
            if button == arcade.MOUSE_BUTTON_LEFT:
                self._focus_plate(hit.activator_index)
            return
        if hit.item is not None and button == arcade.MOUSE_BUTTON_LEFT:
            self._select_kind(hit.item.kind)

    def _link_press(self, cell: tuple[int, int], button: int) -> None:
        index = activator_at(self.document.activators, *cell)
        if button == arcade.MOUSE_BUTTON_RIGHT:
            if index is not None:
                self._delete_plate(index)
                return
            if self._link_index is not None and self.document.can_link(*cell):
                current = self.document.activators[self._link_index]
                if current.has_target(*cell):
                    self.document.toggle_target(self._link_index, *cell)
                    self.notify("bloc delie")
            return
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        if index is not None:
            self._link_index = index
            self._drag_origin = cell
            self._drag_current = cell
            self._resizing_plate = True
            self._placing_plate = False
            self.notify(f"plaque #{index + 1} selectionnee")
            return
        if self._link_index is not None and self.document.can_link(*cell):
            linked = self.document.toggle_target(self._link_index, *cell)
            self.notify("bloc lie" if linked else "bloc delie")
            return
        self._drag_origin = cell
        self._drag_current = cell
        self._placing_plate = True
        self._resizing_plate = False

    def _finish_plate_drag(self) -> None:
        origin = self._drag_origin
        current = self._drag_current or origin
        placing = self._placing_plate
        resizing = self._resizing_plate
        self._placing_plate = False
        self._resizing_plate = False
        self._drag_origin = None
        self._drag_current = None
        if origin is None or current is None:
            return
        plate = _plate_from_drag(origin, current)
        if not self.document.inside(plate.column, plate.row):
            return
        if not self.document.inside(plate.last_column, plate.row):
            return
        if placing:
            clash = overlaps_any(self.document.activators, plate.column, plate.row, plate.width)
            if clash is not None:
                self._focus_plate(clash)
                return
            index = self.document.add_activator(plate.column, plate.row, plate.width)
            self._link_index = index
            self.notify(f"plaque #{index + 1} placee  -  clique un bloc pour le lier")
            return
        if resizing and self._link_index is not None:
            if origin == current:
                return
            clash = overlaps_any(
                self.document.activators,
                plate.column,
                plate.row,
                plate.width,
                skip=self._link_index,
            )
            if clash is not None:
                self.notify("chevauche une autre plaque", settings.COLOR_EDITOR_WARNING)
                return
            current_plate = self.document.activators[self._link_index]
            self.document.replace_activator(
                self._link_index,
                current_plate.resized(plate.column, plate.width),
                "redimensionner une plaque",
            )
            self.notify(f"plaque #{self._link_index + 1} : largeur {plate.width}")

    def _delete_plate(self, index: int) -> None:
        if index < 0 or index >= len(self.document.activators):
            return
        self.document.remove_activator(index)
        if self._link_index is None:
            self.notify("plaque supprimee")
            return
        if self._link_index == index:
            self._link_index = None
        elif self._link_index > index:
            self._link_index -= 1
        self.notify("plaque supprimee")

    def _focus_plate(self, index: int) -> None:
        if index < 0 or index >= len(self.document.activators):
            return
        self.tool = Tool.LINK
        self._link_index = index
        plate = self.document.activators[index]
        self.canvas.center_on(plate.column, plate.row)
        self.notify(f"plaque #{index + 1}  -  clique un bloc pour le lier")

    def _clamp_link_index(self) -> None:
        count = len(self.document.activators)
        if self._link_index is None:
            return
        if count == 0 or self._link_index >= count:
            self._link_index = None


def _plate_from_drag(origin: tuple[int, int], current: tuple[int, int]) -> Activator:
    """Plaque horizontale definie par deux cellules (la ligne de depart compte)."""
    start_column, row = origin
    end_column, _end_row = current
    column = min(start_column, end_column)
    width = abs(end_column - start_column) + 1
    return Activator(column, row, width)


def _slug(value: str) -> str:
    """Nom de fichier ASCII, sans extension."""
    cleaned = []
    for char in value.strip():
        if char.isalnum() or char in "-_":
            cleaned.append(char)
        elif char in " .":
            cleaned.append("_")
    return "".join(cleaned).strip("_")
