"""Interface non-cliquable de l'editeur : barre d'etat, aide, saisie de texte.

Tous les textes passent par `src.ui.labels` : soit le cache de libelles (aide,
titres fixes), soit des `labels.Line` possedees par l'objet (valeurs qui
changent a chaque frame), pour ne jamais appeler `arcade.draw_text` en boucle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import arcade

import settings
from src.ui import labels

# (raccourci, ce que ca fait) : sert a l'aide (F1) et documente l'editeur.
HELP_SECTIONS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Vue",
        (
            ("Clic gauche", "poser l'element"),
            ("Clic droit", "effacer la cellule"),
            ("Molette / + / -", "zoom carte, ou defilement du panneau"),
            ("Clic milieu / Espace", "glisser la vue"),
            ("Fleches / ZQSD", "deplacer la camera"),
            ("Ctrl+G / Origine", "grille / voir toute la carte"),
        ),
    ),
    (
        "Outils",
        (
            ("B / R / G", "pinceau / rectangle / seau"),
            ("X / I / M", "gomme / pipette / selection"),
            ("[ / ]", "element precedent / suivant"),
            ("L / onglet Plaques", "plaques, boutons spectraux, liens"),
            ("V", "plaque sol/esprit, ou bloc tombant fantome"),
            ("Clic sur un lien", "action : cacher / montrer / allumer"),
            ("K / L", "portee du lance-flammes"),
            (", / .", "delay, ou duree du bouton"),
            ("9 / 0", "intervalle lance-flammes, ou respawn"),
            ("H", "pivoter lance-flammes / ressort"),
        ),
    ),
    (
        "Edition",
        (
            ("Ctrl+A", "tout selectionner"),
            ("Ctrl+C / X / V", "copier / couper / coller"),
            ("Entree", "remplir la selection"),
            ("Suppr / Retour", "vider la selection (ou la plaque)"),
            ("Ctrl+R", "remplacer partout le type sous le curseur"),
            ("Ctrl+Z", "annuler"),
            ("Ctrl+Shift+Z / Y", "refaire"),
        ),
    ),
    (
        "Fichier",
        (
            ("Ctrl+S / Shift+S", "enregistrer / enregistrer sous"),
            ("Ctrl+P", "essayer le niveau (Echap pour revenir)"),
            ("F2 / F3 / F4", "nom / indice / dimensions"),
            ("Themes / F5", "terre, sable ou roche"),
            ("Ctrl+O", "liste des cartes"),
            ("Aide / F1", "afficher ou masquer cette aide"),
        ),
    ),
)

SHORTCUTS: tuple[tuple[str, str], ...] = tuple(
    item for _title, items in HELP_SECTIONS for item in items
)


@dataclass(frozen=True, slots=True)
class StatusData:
    """Instantane de l'etat de l'editeur, affiche en bas de l'ecran."""

    filename: str
    name: str
    dirty: bool
    columns: int
    rows: int
    zoom: float
    tool: str
    element: str
    hover: tuple[int, int] | None
    selection: str
    clipboard: str
    undo_label: str
    redo_label: str
    message: str
    message_color: tuple[int, int, int]
    problems: tuple[str, ...]
    plates: str = "-"
    theme: str = ""


class StatusBar:
    """Trois lignes d'information collees en bas de la fenetre."""

    def __init__(self) -> None:
        self._top = labels.Line(settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT)
        self._middle = labels.Line(settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT_DIM)
        self._bottom = labels.Line(settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT_DIM)

    def draw(self, data: StatusData, window_width: float) -> None:
        height = settings.EDITOR_STATUS_HEIGHT
        arcade.draw_lrbt_rectangle_filled(0, window_width, 0, height, settings.COLOR_EDITOR_PANEL)
        arcade.draw_line(0, height, window_width, height, settings.COLOR_EDITOR_PANEL_BORDER, 2)
        marker = "* " if data.dirty else ""
        margin = 16.0
        max_width = max(80.0, window_width - margin * 2)
        self._top.draw(
            f"{marker}{data.filename}   {data.name}   {data.columns}x{data.rows}   "
            f"theme {data.theme}   zoom {data.zoom:.2f}",
            margin,
            height - 32,
            settings.COLOR_EDITOR_WARNING if data.dirty else settings.COLOR_EDITOR_TEXT,
            max_width=max_width,
        )
        cell = f"{data.hover[0]},{data.hover[1]}" if data.hover is not None else "-"
        self._middle.draw(
            f"{data.tool}   {data.element}   cellule {cell}   "
            f"sel {data.selection}   copier {data.clipboard}   plaques {data.plates}",
            margin,
            height - 62,
            max_width=max_width,
        )
        if data.message:
            self._bottom.draw(
                data.message, margin, height - 92, data.message_color, max_width=max_width
            )
        elif data.problems:
            self._bottom.draw(
                f"!  {data.problems[0]}",
                margin,
                height - 92,
                settings.COLOR_EDITOR_WARNING,
                max_width=max_width,
            )
        else:
            self._bottom.draw(
                f"annuler {data.undo_label}   refaire {data.redo_label}   Aide dans le panneau",
                margin,
                height - 92,
                settings.COLOR_EDITOR_TEXT_DIM,
                max_width=max_width,
            )


class HelpOverlay:
    """Liste des raccourcis, par-dessus la carte (F1)."""

    def __init__(self) -> None:
        self.visible = False
        font = settings.EDITOR_UI_FONT
        self._title = labels.Line(
            settings.EDITOR_TITLE_SIZE + 6,
            settings.COLOR_EDITOR_ACCENT,
            anchor_x="center",
            font_name=font,
        )
        self._heading = labels.Line(
            settings.EDITOR_HELP_HEADING,
            settings.COLOR_EDITOR_ACCENT,
            font_name=font,
        )
        self._key_line = labels.Line(
            settings.EDITOR_HELP_SIZE, settings.COLOR_EDITOR_TEXT, font_name=font
        )
        self._desc_line = labels.Line(
            settings.EDITOR_HELP_SIZE, settings.COLOR_EDITOR_TEXT_DIM, font_name=font
        )
        self._footer = labels.Line(
            settings.EDITOR_HELP_SIZE,
            settings.COLOR_EDITOR_TEXT_DIM,
            anchor_x="center",
            font_name=font,
        )

    def toggle(self) -> None:
        self.visible = not self.visible

    def draw(self, window_width: float, window_height: float) -> None:
        if not self.visible:
            return
        arcade.draw_lrbt_rectangle_filled(
            0, window_width, 0, window_height, settings.COLOR_EDITOR_OVERLAY
        )
        rows = _help_rows()
        line_height = float(settings.EDITOR_HELP_LINE)
        heading_extra = 10.0
        pad_x = 28.0
        pad_y = 22.0
        title_h = 48.0
        footer_h = 36.0
        left_rows, right_rows = _split_help_rows(rows, line_height, heading_extra)
        col_h = max(
            _help_block_height(left_rows, line_height, heading_extra),
            _help_block_height(right_rows, line_height, heading_extra),
        )
        panel_w = min(window_width - 48.0, 1080.0)
        panel_h = min(window_height - 48.0, title_h + footer_h + pad_y * 2 + col_h)
        left = (window_width - panel_w) / 2
        bottom = (window_height - panel_h) / 2
        right = left + panel_w
        top = bottom + panel_h
        arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, settings.COLOR_EDITOR_PANEL)
        arcade.draw_lrbt_rectangle_outline(
            left, right, bottom, top, settings.COLOR_EDITOR_ACCENT, 2
        )
        arcade.draw_lrbt_rectangle_filled(
            left, right, top - 4, top, settings.COLOR_EDITOR_ACCENT
        )
        self._title.draw("Aide de l'editeur", (left + right) / 2, top - 36)
        col_width = (panel_w - pad_x * 2) / 2
        key_width = min(188.0, col_width * 0.36)
        gap = 12.0
        desc_width = max(80.0, col_width - key_width - gap)
        body_top = top - title_h
        stop_y = bottom + footer_h
        self._draw_help_column(
            left_rows,
            left + pad_x,
            body_top,
            col_width,
            key_width,
            gap,
            desc_width,
            line_height,
            heading_extra,
            stop_y,
        )
        self._draw_help_column(
            right_rows,
            left + pad_x + col_width,
            body_top,
            col_width,
            key_width,
            gap,
            desc_width,
            line_height,
            heading_extra,
            stop_y,
        )
        self._footer.draw(
            "F1 ou Echap pour fermer",
            (left + right) / 2,
            bottom + 16,
            max_width=panel_w - pad_x * 2,
            overflow="clip",
        )

    def _draw_help_column(
        self,
        rows: list[tuple[str, str, str]],
        x: float,
        top: float,
        col_width: float,
        key_width: float,
        gap: float,
        desc_width: float,
        line_height: float,
        heading_extra: float,
        stop_y: float,
    ) -> None:
        y = top - 6
        stripe = False
        for kind, key, description in rows:
            if y < stop_y + 8:
                break
            if kind == "head":
                y -= heading_extra
                self._heading.draw(key.upper(), x, y, max_width=col_width - 8, overflow="clip")
                y -= line_height
                stripe = False
                continue
            if stripe:
                arcade.draw_lrbt_rectangle_filled(
                    x - 6,
                    x + col_width - 12,
                    y - 8,
                    y + 16,
                    settings.COLOR_EDITOR_HEADING,
                )
            stripe = not stripe
            self._key_line.draw(key, x, y, max_width=key_width, overflow="clip")
            self._desc_line.draw(
                description,
                x + key_width + gap,
                y,
                max_width=desc_width,
                overflow="clip",
            )
            y -= line_height


def _help_rows() -> list[tuple[str, str, str]]:
    """Lignes a dessiner : un titre de section, puis ses raccourcis."""
    rows: list[tuple[str, str, str]] = []
    for title, items in HELP_SECTIONS:
        rows.append(("head", title, ""))
        for key, description in items:
            rows.append(("item", key, description))
    return rows


def _help_block_height(
    rows: list[tuple[str, str, str]], line_height: float, heading_extra: float
) -> float:
    height = 0.0
    for kind, _key, _desc in rows:
        height += line_height
        if kind == "head":
            height += heading_extra
    return height


def _split_help_rows(
    rows: list[tuple[str, str, str]], line_height: float, heading_extra: float
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Coupe entre deux sections pour equivaloir la hauteur des colonnes."""
    heads = [index for index, (kind, _key, _desc) in enumerate(rows) if kind == "head"]
    if len(heads) < 2:
        mid = max(1, len(rows) // 2)
        return rows[:mid], rows[mid:]
    best_cut = heads[1]
    best_diff: float | None = None
    for cut in heads[1:]:
        left_h = _help_block_height(rows[:cut], line_height, heading_extra)
        right_h = _help_block_height(rows[cut:], line_height, heading_extra)
        diff = abs(left_h - right_h)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_cut = cut
    return rows[:best_cut], rows[best_cut:]


class TextPrompt:
    """Saisie modale d'une ligne de texte, ou confirmation oui / non."""

    def __init__(self) -> None:
        self._title = ""
        self._hint = ""
        self._value = ""
        self._confirm = False
        self._active = False
        self._on_submit: Callable[[str], None] | None = None
        self._value_line = labels.Line(settings.EDITOR_TITLE_SIZE, settings.COLOR_EDITOR_ACCENT)
        self._title_line = labels.Line(settings.EDITOR_TITLE_SIZE, settings.COLOR_EDITOR_TEXT)
        self._hint_line = labels.Line(settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT_DIM)

    @property
    def active(self) -> bool:
        return self._active

    def ask(
        self,
        title: str,
        value: str,
        on_submit: Callable[[str], None],
        hint: str = "Entree pour valider, Echap pour annuler",
    ) -> None:
        """Ouvre une saisie de texte pre-remplie."""
        if not title:
            raise ValueError("title ne doit pas etre vide")
        self._title = title
        self._value = value
        self._hint = hint
        self._confirm = False
        self._active = True
        self._on_submit = on_submit

    def confirm(self, title: str, on_yes: Callable[[str], None]) -> None:
        """Ouvre une confirmation : O pour oui, toute autre touche pour non."""
        self.ask(title, "", on_yes, hint="O pour confirmer, Echap pour annuler")
        self._confirm = True

    def close(self) -> None:
        self._active = False
        self._on_submit = None

    def _submit(self) -> None:
        """Valide la saisie : ferme la prompt puis appelle le callback."""
        callback = self._on_submit
        value = self._value
        self.close()
        if callback is not None:
            callback(value)

    def on_text(self, text: str) -> None:
        """Ajoute les caracteres tapes (ignores en mode confirmation)."""
        if not self._active or self._confirm:
            return
        self._value += "".join(char for char in text if char.isprintable())

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        """Traite une touche. Retourne True si la saisie l'a consommee."""
        if not self._active:
            return False
        if symbol == arcade.key.ESCAPE:
            self.close()
            return True
        if self._confirm:
            if symbol in (arcade.key.O, arcade.key.Y, arcade.key.ENTER, arcade.key.RETURN):
                self._submit()
            else:
                self.close()
            return True
        if symbol == arcade.key.BACKSPACE:
            self._value = self._value[:-1]
            return True
        if symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER):
            self._submit()
            return True
        return True  # une saisie ouverte capture tout le clavier

    def draw(self, window_width: float, window_height: float) -> None:
        if not self._active:
            return
        box_width = min(840.0, window_width - 80)
        box_height = 168.0
        left = (window_width - box_width) / 2
        bottom = (window_height - box_height) / 2
        arcade.draw_lrbt_rectangle_filled(
            0, window_width, 0, window_height, settings.COLOR_EDITOR_OVERLAY
        )
        arcade.draw_lrbt_rectangle_filled(
            left, left + box_width, bottom, bottom + box_height, settings.COLOR_EDITOR_PANEL
        )
        arcade.draw_lrbt_rectangle_outline(
            left,
            left + box_width,
            bottom,
            bottom + box_height,
            settings.COLOR_EDITOR_ACCENT,
            2,
        )
        inner = box_width - 48
        self._title_line.draw(
            self._title, left + 24, bottom + box_height - 44, max_width=inner
        )
        shown = self._value if self._confirm else f"{self._value}_"
        self._value_line.draw(
            shown,
            left + 24,
            bottom + box_height - 88,
            max_width=inner,
            overflow="end",
        )
        self._hint_line.draw(self._hint, left + 24, bottom + 28, max_width=inner)
