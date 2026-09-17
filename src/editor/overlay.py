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
    ("Molette / + / -", "zoomer (carte) / defiler (panneau)"),
    ("Clic milieu / Espace", "glisser la vue"),
    ("Fleches / ZQSD", "deplacer la camera"),
    ("B / R / G", "pinceau / rectangle / remplir la zone"),
    ("X / I / M", "gomme / pipette / selection"),
    ("L / onglet Plaques", "plaques et blocs lies"),
    ("V / bouton cache-montre", "inverser la plaque (disparait / apparait)"),
    (", et .", "portee du lance-flammes / delay du bloc tombant"),
    ("9 et 0", "intervalle du lance-flammes / respawn du bloc tombant"),
    ("H", "pivoter le lance-flammes (4 directions)"),
    ("[ et ]", "element precedent / suivant de la palette"),
    ("Ctrl+A", "tout selectionner"),
    ("Ctrl+C / Ctrl+X", "copier / couper la selection"),
    ("Ctrl+V", "coller sous le curseur"),
    ("Entree", "remplir la selection avec l'element courant"),
    ("Suppr / Retour", "vider la selection (ou la plaque)"),
    ("Ctrl+R", "remplacer partout le type sous le curseur"),
    ("Ctrl+Z", "annuler"),
    ("Ctrl+Shift+Z / Ctrl+Y", "refaire"),
    ("Ctrl+S / Ctrl+Shift+S", "enregistrer / enregistrer sous"),
    ("Ctrl+P", "essayer le niveau (Echap pour revenir)"),
    ("F2 / F3 / F4", "nom / indice / dimensions"),
    ("themes du panneau / F5", "theme du terrain (terre / sable / roche)"),
    ("Ctrl+G / Origine", "grille / voir toute la carte"),
    ("Ctrl+O", "revenir a la liste des cartes"),
    ("Aide / F1", "afficher / masquer cette aide"),
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
        self._key_line = labels.Line(settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT)
        self._desc_line = labels.Line(
            settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT_DIM
        )
        self._footer = labels.Line(
            settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT_DIM, anchor_x="center"
        )

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
            window_height - 56,
            settings.EDITOR_TITLE_SIZE + 4,
            settings.COLOR_EDITOR_ACCENT,
            anchor_x="center",
        )
        margin = 48.0
        gap = 16.0
        column_width = window_width / 2
        key_width = min(260.0, max(96.0, column_width * 0.40))
        desc_width = max(80.0, column_width - key_width - gap - margin)
        top = window_height - 108
        line_height = 32
        per_column = (len(SHORTCUTS) + 1) // 2
        for index, (keys, description) in enumerate(SHORTCUTS):
            column = index // per_column
            row = index % per_column
            x = margin + column * column_width
            y = top - row * line_height
            self._key_line.draw(keys, x, y, max_width=key_width)
            self._desc_line.draw(
                description, x + key_width + gap, y, max_width=desc_width
            )
        self._footer.draw(
            "Aide ou Echap pour fermer",
            window_width / 2,
            36,
            max_width=max(80.0, window_width - margin * 2),
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
