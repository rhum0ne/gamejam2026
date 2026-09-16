"""Pile d'annulation de l'editeur : Ctrl+Z / Ctrl+Shift+Z.

Une action (`Edit`) est soit une liste de changements de cellules (le cas
courant : pinceau, rectangle, collage, suppression en masse), soit un
changement de forme de la grille (redimensionnement), auquel cas la grille
complete est memorisee avant et apres.

Ce module ne connait pas le document : il ne stocke que des donnees. C'est
`EditorDocument` qui sait appliquer un `Edit` dans un sens ou dans l'autre.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import settings
from src.editor.activators import Activator


@dataclass(frozen=True, slots=True)
class CellChange:
    """Une cellule qui passe de `before` a `after`."""

    column: int
    row: int
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class GridState:
    """Grille complete, memorisee avant / apres un redimensionnement."""

    cells: tuple[tuple[str, ...], ...]

    @property
    def columns(self) -> int:
        return len(self.cells[0]) if self.cells else 0

    @property
    def rows(self) -> int:
        return len(self.cells)


@dataclass(frozen=True, slots=True)
class Edit:
    """Une entree annulable de l'historique."""

    label: str
    changes: tuple[CellChange, ...] = ()
    before: GridState | None = None
    after: GridState | None = None
    activators_before: tuple[Activator, ...] | None = None
    activators_after: tuple[Activator, ...] | None = None

    @property
    def reshapes(self) -> bool:
        """Indique si l'action change la forme de la grille."""
        return self.before is not None and self.after is not None

    @property
    def retargets(self) -> bool:
        """Indique si l'action change les plaques / liens."""
        return self.activators_before is not None and self.activators_after is not None

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("label ne doit pas etre vide")
        if not self.changes and not self.reshapes and not self.retargets:
            raise ValueError("une action doit changer au moins une cellule")


@dataclass(slots=True)
class History:
    """Deux piles : ce qui peut etre annule, ce qui peut etre refait."""

    limit: int = settings.EDITOR_HISTORY_LIMIT
    _undo: deque[Edit] = field(default_factory=deque)
    _redo: list[Edit] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("limit doit valoir au moins 1")

    def push(self, edit: Edit) -> None:
        """Empile une action et abandonne la branche de redo."""
        self._undo.append(edit)
        while len(self._undo) > self.limit:
            self._undo.popleft()
        self._redo.clear()

    def undo(self) -> Edit | None:
        """Retire et retourne la derniere action, ou None si la pile est vide."""
        if not self._undo:
            return None
        edit = self._undo.pop()
        self._redo.append(edit)
        return edit

    def redo(self) -> Edit | None:
        """Retire et retourne la derniere action annulee, ou None."""
        if not self._redo:
            return None
        edit = self._redo.pop()
        self._undo.append(edit)
        return edit

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_label(self) -> str:
        return self._undo[-1].label if self._undo else "-"

    @property
    def redo_label(self) -> str:
        return self._redo[-1].label if self._redo else "-"

    @property
    def depth(self) -> int:
        return len(self._undo)
