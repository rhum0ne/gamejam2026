"""Liste des cartes : creer, ouvrir, dupliquer, renommer, supprimer.

Les fichiers sont ceux de `assets/maps/` (glob `settings.EDITOR_MAPS_GLOB`).
Ajouter une carte, c'est ecrire un JSON dans ce dossier : elle apparait ici
au prochain affichage, sans autre declaration.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import arcade

import settings
from src.editor.document import DocumentError, EditorDocument
from src.editor.edit_view import EditView, _slug
from src.editor.overlay import TextPrompt
from src.ui import labels
from src.ui.display import handle_display_key, use_default_camera


def list_maps() -> list[Path]:
    """Cartes JSON du dossier `assets/maps/`, triees par nom."""
    settings.MAPS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        path for path in settings.MAPS_DIR.glob(settings.EDITOR_MAPS_GLOB) if path.is_file()
    )


class BrowserView(arcade.View):
    """Ecran d'accueil de l'editeur : une ligne par carte."""

    def __init__(self) -> None:
        super().__init__()
        self.background_color = settings.COLOR_EDITOR_BACKGROUND
        self.prompt = TextPrompt()
        self._maps: list[Path] = []
        self._index = 0
        self._message = "Entree : ouvrir  -  N : nouveau  -  D : dupliquer  -  F2 : renommer  -  Suppr : supprimer"
        self._message_color = settings.COLOR_EDITOR_TEXT_DIM
        self._title = labels.Line(settings.EDITOR_TITLE_SIZE + 4, settings.COLOR_EDITOR_ACCENT)
        self._hint = labels.Line(settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT_DIM)
        self._row = labels.Line(settings.EDITOR_TEXT_SIZE, settings.COLOR_EDITOR_TEXT)
        self._refresh()

    def on_show_view(self) -> None:
        use_default_camera(self.window)
        self._refresh()

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)

    def _refresh(self) -> None:
        self._maps = list_maps()
        if self._maps:
            self._index = max(0, min(self._index, len(self._maps) - 1))
        else:
            self._index = 0

    def on_draw(self) -> None:
        use_default_camera(self.window)
        self.clear()
        width = float(self.window.width)
        height = float(self.window.height)
        self._title.draw("EDITEUR DE NIVEAUX", 48, height - 56)
        self._hint.draw(self._message, 48, height - 84, self._message_color)
        if not self._maps:
            self._row.draw(
                "Aucune carte. Appuie sur N pour en creer une.",
                48,
                height - 140,
                settings.COLOR_EDITOR_WARNING,
            )
        else:
            self._draw_rows(height)
        labels.draw(
            "Echap pour quitter l'editeur",
            48,
            28,
            settings.EDITOR_TEXT_SIZE,
            settings.COLOR_EDITOR_TEXT_DIM,
        )
        self.prompt.draw(width, height)

    def _draw_rows(self, height: float) -> None:
        top = height - 130
        row_height = settings.EDITOR_ROW_HEIGHT
        for index, path in enumerate(self._maps):
            y = top - index * row_height
            if y < 50:
                break
            if index == self._index:
                arcade.draw_lrbt_rectangle_filled(
                    36, self.window.width - 36, y - 8, y + 22, settings.COLOR_EDITOR_ROW_ACTIVE
                )
            color = (
                settings.COLOR_EDITOR_TEXT if index == self._index else settings.COLOR_EDITOR_TEXT_DIM
            )
            self._row.draw(f"{path.name}", 56, y, color)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        if self.prompt.active or button != arcade.MOUSE_BUTTON_LEFT:
            return
        index = self._index_at(y)
        if index is None:
            return
        self._index = index
        self._open_current()

    def _index_at(self, y: float) -> int | None:
        top = self.window.height - 130
        row_height = settings.EDITOR_ROW_HEIGHT
        for index in range(len(self._maps)):
            row_y = top - index * row_height
            if row_y - 8 <= y <= row_y + 22:
                return index
        return None

    def on_text(self, text: str) -> None:
        self.prompt.on_text(text)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if self.prompt.on_key_press(symbol, modifiers):
            return
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.ESCAPE:
            self.window.close()
            return
        if symbol in (arcade.key.UP, arcade.key.Z, arcade.key.W):
            self._move(-1)
            return
        if symbol in (arcade.key.DOWN, arcade.key.S):
            self._move(1)
            return
        if symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER, arcade.key.E):
            self._open_current()
            return
        if symbol == arcade.key.N:
            self._ask_new()
            return
        if symbol == arcade.key.D:
            self._duplicate()
            return
        if symbol == arcade.key.F2:
            self._ask_rename()
            return
        if symbol in (arcade.key.DELETE, arcade.key.BACKSPACE):
            self._ask_delete()

    def _move(self, step: int) -> None:
        if not self._maps:
            return
        self._index = (self._index + step) % len(self._maps)

    def _open_current(self) -> None:
        if not self._maps:
            self._ask_new()
            return
        path = self._maps[self._index]
        try:
            document = EditorDocument.from_file(path)
        except DocumentError as error:
            self._tell(str(error), settings.COLOR_EDITOR_DANGER)
            return
        self.window.show_view(EditView(document))

    def _ask_new(self) -> None:
        self.prompt.ask("Nom du nouveau niveau", "Nouveau niveau", self._create)

    def _create(self, value: str) -> None:
        name = value.strip() or "Nouveau niveau"
        document = EditorDocument.new(name=name)
        self.window.show_view(EditView(document))

    def _duplicate(self) -> None:
        if not self._maps:
            return
        source = self._maps[self._index]
        target = _unique_path(source.stem + "_copie")
        shutil.copy2(source, target)
        self._refresh()
        self._index = self._maps.index(target)
        self._tell(f"copie : {target.name}")

    def _ask_rename(self) -> None:
        if not self._maps:
            return
        self.prompt.ask(
            "Nouveau nom de fichier (sans .json)",
            self._maps[self._index].stem,
            self._rename,
        )

    def _rename(self, value: str) -> None:
        if not self._maps:
            return
        name = _slug(value)
        if not name:
            self._tell("nom vide", settings.COLOR_EDITOR_DANGER)
            return
        source = self._maps[self._index]
        target = settings.MAPS_DIR / f"{name}.json"
        if target.exists() and target.resolve() != source.resolve():
            self._tell("ce nom existe deja", settings.COLOR_EDITOR_DANGER)
            return
        source.rename(target)
        self._refresh()
        self._index = self._maps.index(target)
        self._tell(f"renomme : {target.name}")

    def _ask_delete(self) -> None:
        if not self._maps:
            return
        name = self._maps[self._index].name
        self.prompt.confirm(f"Supprimer {name} ? Cette action est definitive.", self._delete)

    def _delete(self, _value: str) -> None:
        if not self._maps:
            return
        path = self._maps[self._index]
        path.unlink()
        self._tell(f"supprime : {path.name}", settings.COLOR_EDITOR_WARNING)
        self._refresh()

    def _tell(self, text: str, color: tuple[int, int, int] = settings.COLOR_EDITOR_OK) -> None:
        self._message = text
        self._message_color = color


def _unique_path(stem: str) -> Path:
    """Chemin libre dans `assets/maps/`, en ajoutant un numero si besoin."""
    candidate = settings.MAPS_DIR / f"{stem}.json"
    index = 2
    while candidate.exists():
        candidate = settings.MAPS_DIR / f"{stem}_{index}.json"
        index += 1
    return candidate
