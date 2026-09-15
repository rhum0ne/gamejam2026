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
SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("Clic gauche", "poser l'element selectionne"),
    ("Clic droit", "effacer la cellule"),
    ("Molette / + / -", "zoomer (survol carte) / defiler (survol palette)"),
    ("Clic milieu / Espace", "deplacer la vue"),
    ("Fleches / ZQSD", "deplacer la vue"),
    ("B / R / G", "pinceau / rectangle / remplir la zone"),
    ("X / I / M", "gomme / pipette / selection"),
    ("[ et ]", "element precedent / suivant de la palette"),
    ("Ctrl+A", "tout selectionner"),
    ("Ctrl+C / Ctrl+X", "copier / couper la selection"),
    ("Ctrl+V", "coller sous le curseur"),
    ("Entree", "remplir la selection avec l'element courant"),
    ("Suppr / Retour", "vider la selection"),
    ("Ctrl+R", "remplacer partout le type sous le curseur"),
    ("Ctrl+Z", "annuler"),
    ("Ctrl+Shift+Z / Ctrl+Y", "refaire"),
    ("Ctrl+S / Ctrl+Shift+S", "enregistrer / enregistrer sous"),
    ("Ctrl+P", "essayer le niveau (Echap pour revenir)"),
    ("F2 / F3 / F4", "nom / indice / dimensions"),
    ("Ctrl+G / Origine", "grille / voir toute la carte"),
    ("Ctrl+O", "revenir a la liste des cartes"),
    ("F1", "afficher / masquer cette aide"),
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
        marker = "*" if data.dirty else ""
        self._top.draw(
            f"{marker}{data.filename}  -  {data.name}  -  {data.columns}x{data.rows} tuiles"
            f"  -  zoom {data.zoom:.2f}",
            14,
            height - 22,
            settings.COLOR_EDITOR_WARNING if data.dirty else settings.COLOR_EDITOR_TEXT,
        )
        cell = f"{data.hover[0]},{data.hover[1]}" if data.hover is not None else "-"
        self._middle.draw(
            f"outil {data.tool}  -  element {data.element}  -  cellule {cell}"
            f"  -  selection {data.selection}  -  presse-papiers {data.clipboard}",
            14,
            height - 42,
        )
        if data.message:
            self._bottom.draw(data.message, 14, height - 62, data.message_color)
        elif data.problems:
            self._bottom.draw(
                f"attention : {data.problems[0]}", 14, height - 62, settings.COLOR_EDITOR_WARNING
            )
        else:
            self._bottom.draw(
                f"annuler : {data.undo_label}  -  refaire : {data.redo_label}  -  F1 : aide",
                14,
                height - 62,
                settings.COLOR_EDITOR_TEXT_DIM,
            )


class HelpOverlay:
    """Liste des raccourcis, par-dessus la carte (F1)."""

    def __init__(self) -> None:
        self.visible = False

    def toggle(self) -> None:
        self.visible = not self.visible

    def draw(self, window_width: float, window_height: float) -> None:
        if not self.visible:
            return
        arcade.draw_lrbt_rectangle_filled(
            0, window_width, 0, window_height, settings.COLOR_EDITOR_OVERLAY
        )
        labels.draw(
            "RACCOURCIS DE L'EDITEUR",
            window_width / 2,
            window_height - 60,
            settings.EDITOR_TITLE_SIZE + 3,
            settings.COLOR_EDITOR_ACCENT,
            anchor_x="center",
        )
        column_width = window_width / 2
        top = window_height - 110
        line_height = 26
        per_column = (len(SHORTCUTS) + 1) // 2
        for index, (keys, description) in enumerate(SHORTCUTS):
            column = index // per_column
            row = index % per_column
            x = 60 + column * column_width
            y = top - row * line_height
            labels.draw(keys, x, y, settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT)
            labels.draw(
                description,
                x + 210,
                y,
                settings.EDITOR_TEXT_SIZE,
                settings.COLOR_EDITOR_TEXT_DIM,
            )
        labels.draw(
            "F1 ou Echap pour fermer",
            window_width / 2,
            40,
            settings.EDITOR_TEXT_SIZE,
            settings.COLOR_EDITOR_TEXT_DIM,
            anchor_x="center",
        )


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
        box_width = min(720.0, window_width - 80)
        box_height = 150.0
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
        self._title_line.draw(self._title, left + 24, bottom + box_height - 40)
        shown = self._value if self._confirm else f"{self._value}_"
        self._value_line.draw(shown[-46:], left + 24, bottom + box_height - 80)
        self._hint_line.draw(self._hint, left + 24, bottom + 26)

    def _submit(self) -> None:
        callback = self._on_submit
        value = self._value
        self.close()
        if callback is not None:
            callback(value)
