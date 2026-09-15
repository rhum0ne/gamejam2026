"""Carte en cours d'edition : grille de types, metadonnees, lecture/ecriture JSON.

Le document ne manipule **pas** de symboles : chaque cellule contient le nom du
type (`"rock"`, `"enemy"`, `""` pour du vide). Les symboles de legende ne sont
choisis qu'a l'ecriture, ce qui evite les collisions et permet de changer un
symbole sans toucher a la carte. Les symboles lus dans un fichier sont
conserves pour que reecrire une carte existante ne bouleverse pas son diff.

Toutes les methodes d'edition retournent la liste des cellules touchees
(`CellState`) : le rendu n'a plus qu'a mettre a jour ces cellules-la, sans
reconstruire toute la grille. Un changement de forme (redimensionnement)
incremente `layout_version` a la place : c'est le signal d'une reconstruction.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

import settings
from src.editor import palette
from src.editor.history import CellChange, Edit, GridState, History
from src.editor.selection import Block, GridRect

# (colonne, ligne, type present apres l'operation)
CellState = tuple[int, int, str]

# Types dont une seule occurrence a un sens : en poser un nouveau retire l'ancien.
_UNIQUE_KINDS = frozenset({"player_spawn"})


class DocumentError(ValueError):
    """Fichier de carte illisible ou incoherent."""


class EditorDocument:
    """Grille editable d'une carte, avec son historique d'annulation."""

    def __init__(
        self,
        *,
        name: str,
        hint: str,
        tile_size: int,
        cells: Sequence[Sequence[str]],
        path: Path | None = None,
        symbols: dict[str, str] | None = None,
    ) -> None:
        if not cells or not cells[0]:
            raise DocumentError("une carte doit avoir au moins une cellule")
        widths = {len(row) for row in cells}
        if len(widths) != 1:
            raise DocumentError(f"lignes de longueurs differentes : {sorted(widths)}")
        if tile_size <= 0:
            raise DocumentError("tile_size doit etre strictement positif")
        self.name = name
        self.hint = hint
        self.tile_size = tile_size
        self.path = path
        self.history = History()
        self._cells: list[list[str]] = [list(row) for row in cells]
        self._symbols: dict[str, str] = dict(palette.preferred_symbols())
        if symbols:
            self._symbols.update(symbols)
        self._version = 0
        self._layout_version = 0
        self._saved_version = 0
        self._stroke: list[CellChange] | None = None
        self._stroke_label = ""

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def new(
        cls,
        name: str = "Nouveau niveau",
        columns: int = settings.EDITOR_NEW_COLUMNS,
        rows: int = settings.EDITOR_NEW_ROWS,
        tile_size: int = settings.TILE_SIZE,
    ) -> "EditorDocument":
        """Carte vide, entouree d'un cadre de roche pour ne pas tomber hors monde."""
        columns = max(settings.EDITOR_MIN_COLUMNS, min(settings.EDITOR_MAX_COLUMNS, columns))
        rows = max(settings.EDITOR_MIN_ROWS, min(settings.EDITOR_MAX_ROWS, rows))
        cells = [[palette.EMPTY] * columns for _ in range(rows)]
        for column in range(columns):
            cells[0][column] = "rock"
            cells[rows - 1][column] = "bedrock"
        for row in range(rows):
            cells[row][0] = "rock"
            cells[row][columns - 1] = "rock"
        cells[rows - 2][2] = "player_spawn"
        return cls(name=name, hint="", tile_size=tile_size, cells=cells)

    @classmethod
    def from_file(cls, path: str | Path) -> "EditorDocument":
        """Charge une carte JSON de `assets/maps/` (ou un chemin absolu)."""
        map_path = Path(path)
        if not map_path.is_absolute():
            map_path = settings.MAPS_DIR / map_path
        if not map_path.is_file():
            raise DocumentError(f"carte introuvable : {map_path}")
        try:
            data = json.loads(map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DocumentError(f"carte illisible ({map_path.name}) : {error}") from error
        return cls.from_dict(data, path=map_path)

    @classmethod
    def from_dict(cls, data: dict, path: Path | None = None) -> "EditorDocument":
        grid = data.get("rows")
        if not isinstance(grid, list) or not grid:
            raise DocumentError("la carte ne contient aucune ligne ('rows')")
        legend = data.get("legend", {})
        if not isinstance(legend, dict):
            raise DocumentError("'legend' doit etre un objet symbole -> type")
        cells: list[list[str]] = []
        for row_index, row in enumerate(grid):
            if not isinstance(row, str):
                raise DocumentError(f"la ligne {row_index} n'est pas une chaine")
            line: list[str] = []
            for column_index, symbol in enumerate(row):
                kind = legend.get(symbol, palette.EMPTY_KIND if symbol == "." else None)
                if kind is None:
                    raise DocumentError(
                        f"symbole '{symbol}' absent de la legende "
                        f"(ligne {row_index}, colonne {column_index})"
                    )
                line.append(palette.EMPTY if kind == palette.EMPTY_KIND else kind)
            cells.append(line)
        symbols = {
            kind: symbol
            for symbol, kind in legend.items()
            if kind != palette.EMPTY_KIND and symbol != "."
        }
        return cls(
            name=str(data.get("name", "Niveau sans nom")),
            hint=str(data.get("hint", "")),
            tile_size=int(data.get("tile_size", settings.TILE_SIZE)),
            cells=cells,
            path=path,
            symbols=symbols,
        )

    # ------------------------------------------------------------------ #
    # Etat
    # ------------------------------------------------------------------ #

    @property
    def columns(self) -> int:
        return len(self._cells[0])

    @property
    def rows(self) -> int:
        return len(self._cells)

    @property
    def version(self) -> int:
        """Compteur incremente a chaque modification."""
        return self._version

    @property
    def layout_version(self) -> int:
        """Compteur incremente quand la grille change de forme."""
        return self._layout_version

    @property
    def dirty(self) -> bool:
        return self._version != self._saved_version

    @property
    def filename(self) -> str:
        return self.path.name if self.path is not None else "(jamais enregistre)"

    def inside(self, column: int, row: int) -> bool:
        return 0 <= column < self.columns and 0 <= row < self.rows

    def cell(self, column: int, row: int) -> str:
        """Type present dans une cellule, ou `EMPTY` hors de la carte."""
        if not self.inside(column, row):
            return palette.EMPTY
        return self._cells[row][column]

    def counts(self) -> dict[str, int]:
        """Nombre de cellules par type present dans la carte."""
        tally: dict[str, int] = {}
        for row in self._cells:
            for kind in row:
                if kind:
                    tally[kind] = tally.get(kind, 0) + 1
        return tally

    def problems(self) -> tuple[str, ...]:
        """Anomalies qui empecheraient (ou gacheraient) le chargement en jeu."""
        tally = self.counts()
        issues: list[str] = []
        spawns = tally.get("player_spawn", 0)
        if spawns == 0:
            issues.append("aucun depart joueur : le niveau demarrera en (0, 0)")
        elif spawns > 1:
            issues.append(f"{spawns} departs joueur : seul le dernier comptera")
        if not tally.get("door"):
            issues.append("aucune porte : le niveau est infinissable")
        if not tally.get("checkpoint"):
            issues.append("aucun checkpoint : la reapparition se fera au depart")
        unknown = sorted(kind for kind in tally if not palette.is_known(kind))
        if unknown:
            issues.append(f"types inconnus du jeu : {', '.join(unknown)}")
        return tuple(issues)

    def block(self, rect: GridRect) -> Block | None:
        """Copie la zone `rect`, ou None si elle est hors carte."""
        clamped = rect.clamped(self.columns, self.rows)
        if clamped is None:
            return None
        return Block.from_rows(
            [
                self._cells[row][clamped.min_column : clamped.max_column + 1]
                for row in range(clamped.min_row, clamped.max_row + 1)
            ]
        )

    # ------------------------------------------------------------------ #
    # Edition
    # ------------------------------------------------------------------ #

    def begin_stroke(self, label: str) -> None:
        """Ouvre un groupe : tout ce qui suit ne fera qu'une seule annulation."""
        if self._stroke is None:
            self._stroke = []
            self._stroke_label = label

    def end_stroke(self) -> None:
        """Ferme le groupe ouvert par `begin_stroke` et l'empile s'il a servi."""
        pending = self._stroke
        self._stroke = None
        if pending:
            self.history.push(Edit(label=self._stroke_label, changes=tuple(pending)))

    def paint(
        self,
        cells: Iterable[tuple[int, int]],
        kind: str,
        label: str = "peindre",
    ) -> tuple[CellState, ...]:
        """Ecrit `kind` (ou `EMPTY` pour effacer) dans les cellules demandees."""
        targets = [(column, row) for column, row in cells if self.inside(column, row)]
        if not targets:
            return ()
        changes: list[CellChange] = []
        if kind in _UNIQUE_KINDS:
            keep = set(targets[-1:])
            changes.extend(self._erase_kind(kind, skip=keep))
        for column, row in targets:
            current = self._cells[row][column]
            if current == kind:
                continue
            self._cells[row][column] = kind
            changes.append(CellChange(column, row, current, kind))
        return self._record(label, changes)

    def fill_rect(self, rect: GridRect, kind: str) -> tuple[CellState, ...]:
        """Remplit un rectangle (ajout en masse, ou suppression si `kind` est vide)."""
        clamped = rect.clamped(self.columns, self.rows)
        if clamped is None:
            return ()
        label = "effacer la zone" if not kind else "remplir la zone"
        return self.paint(clamped.cells(), kind, label)

    def fill_area(self, column: int, row: int, kind: str) -> tuple[CellState, ...]:
        """Remplissage par zone : propage `kind` sur les cellules voisines identiques."""
        if not self.inside(column, row):
            return ()
        origin = self._cells[row][column]
        if origin == kind:
            return ()
        stack = [(column, row)]
        seen = {(column, row)}
        targets: list[tuple[int, int]] = []
        while stack and len(targets) < settings.EDITOR_FLOOD_LIMIT:
            current_column, current_row = stack.pop()
            if self._cells[current_row][current_column] != origin:
                continue
            targets.append((current_column, current_row))
            for next_column, next_row in (
                (current_column + 1, current_row),
                (current_column - 1, current_row),
                (current_column, current_row + 1),
                (current_column, current_row - 1),
            ):
                if (next_column, next_row) in seen or not self.inside(next_column, next_row):
                    continue
                seen.add((next_column, next_row))
                stack.append((next_column, next_row))
        return self.paint(targets, kind, "remplir la zone")

    def replace_kind(
        self,
        old_kind: str,
        new_kind: str,
        rect: GridRect | None = None,
    ) -> tuple[CellState, ...]:
        """Remplace toutes les occurrences d'un type (dans `rect` si fourni)."""
        if old_kind == new_kind:
            return ()
        area = rect.clamped(self.columns, self.rows) if rect else GridRect.whole(self.columns, self.rows)
        if area is None:
            return ()
        targets = [
            (column, row) for column, row in area.cells() if self._cells[row][column] == old_kind
        ]
        return self.paint(targets, new_kind, "remplacer un type")

    def stamp(
        self,
        column: int,
        row: int,
        block: Block,
        *,
        keep_empty: bool = False,
    ) -> tuple[CellState, ...]:
        """Colle un bloc, coin haut-gauche en (`column`, `row`).

        `keep_empty` a False laisse le decor existant sous les cellules vides du
        bloc : c'est le comportement attendu quand on tamponne un motif.
        """
        changes: list[CellChange] = []
        for block_row, line in enumerate(block.cells):
            target_row = row + block_row
            for block_column, kind in enumerate(line):
                target_column = column + block_column
                if not self.inside(target_column, target_row):
                    continue
                if keep_empty and not kind:
                    continue
                current = self._cells[target_row][target_column]
                if current == kind:
                    continue
                self._cells[target_row][target_column] = kind
                changes.append(CellChange(target_column, target_row, current, kind))
        return self._record("coller", changes)

    def resize(self, columns: int, rows: int) -> bool:
        """Change les dimensions de la carte en gardant le coin haut-gauche.

        Retourne False si les dimensions demandees sont deja celles en place.
        """
        columns = max(settings.EDITOR_MIN_COLUMNS, min(settings.EDITOR_MAX_COLUMNS, columns))
        rows = max(settings.EDITOR_MIN_ROWS, min(settings.EDITOR_MAX_ROWS, rows))
        if columns == self.columns and rows == self.rows:
            return False
        before = self._snapshot()
        resized = [
            [
                self._cells[row][column] if row < self.rows and column < self.columns else palette.EMPTY
                for column in range(columns)
            ]
            for row in range(rows)
        ]
        self._cells = resized
        after = self._snapshot()
        self.history.push(Edit(label="redimensionner", before=before, after=after))
        self._version += 1
        self._layout_version += 1
        return True

    def set_metadata(
        self,
        *,
        name: str | None = None,
        hint: str | None = None,
        tile_size: int | None = None,
    ) -> None:
        """Change le nom, l'indice ou la taille de tuile (hors historique)."""
        if name is not None:
            self.name = name
        if hint is not None:
            self.hint = hint
        if tile_size is not None:
            if tile_size <= 0:
                raise ValueError("tile_size doit etre strictement positif")
            self.tile_size = tile_size
            self._layout_version += 1
        self._version += 1

    # ------------------------------------------------------------------ #
    # Annuler / refaire
    # ------------------------------------------------------------------ #

    def undo(self) -> tuple[CellState, ...] | None:
        """Annule la derniere action. None si l'historique est vide."""
        edit = self.history.undo()
        if edit is None:
            return None
        return self._replay(edit, forward=False)

    def redo(self) -> tuple[CellState, ...] | None:
        """Refait la derniere action annulee. None s'il n'y a rien a refaire."""
        edit = self.history.redo()
        if edit is None:
            return None
        return self._replay(edit, forward=True)

    # ------------------------------------------------------------------ #
    # Ecriture
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        """Carte au format attendu par `Level.from_dict`."""
        assigned = self._assign_symbols()
        legend = {".": palette.EMPTY_KIND}
        legend.update({assigned[kind]: kind for kind in sorted(assigned)})
        rows = ["".join(assigned[kind] if kind else "." for kind in row) for row in self._cells]
        return {
            "name": self.name,
            "hint": self.hint,
            "tile_size": self.tile_size,
            "legend": legend,
            "rows": rows,
        }

    def save(self, path: str | Path | None = None) -> Path:
        """Ecrit la carte sur disque et retourne le chemin utilise."""
        target = Path(path) if path is not None else self.path
        if target is None:
            raise DocumentError("aucun chemin d'enregistrement connu")
        if not target.is_absolute():
            target = settings.MAPS_DIR / target
        if target.suffix != ".json":
            target = target.with_suffix(".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        target.write_text(f"{payload}\n", encoding="utf-8")
        self.path = target
        self._saved_version = self._version
        return target

    # ------------------------------------------------------------------ #
    # Interne
    # ------------------------------------------------------------------ #

    def _record(self, label: str, changes: list[CellChange]) -> tuple[CellState, ...]:
        if not changes:
            return ()
        if self._stroke is not None:
            self._stroke.extend(changes)
        else:
            self.history.push(Edit(label=label, changes=tuple(changes)))
        self._version += 1
        return tuple((change.column, change.row, change.after) for change in changes)

    def _erase_kind(self, kind: str, skip: set[tuple[int, int]]) -> list[CellChange]:
        changes: list[CellChange] = []
        for row, line in enumerate(self._cells):
            for column, current in enumerate(line):
                if current != kind or (column, row) in skip:
                    continue
                line[column] = palette.EMPTY
                changes.append(CellChange(column, row, current, palette.EMPTY))
        return changes

    def _replay(self, edit: Edit, *, forward: bool) -> tuple[CellState, ...]:
        self._version += 1
        if edit.reshapes:
            state = edit.after if forward else edit.before
            assert state is not None  # garanti par Edit.reshapes
            self._cells = [list(row) for row in state.cells]
            self._layout_version += 1
            return ()
        states: list[CellState] = []
        for change in edit.changes:
            value = change.after if forward else change.before
            self._cells[change.row][change.column] = value
            states.append((change.column, change.row, value))
        return tuple(states)

    def _snapshot(self) -> GridState:
        return GridState(tuple(tuple(row) for row in self._cells))

    def _assign_symbols(self) -> dict[str, str]:
        """Choisit un symbole de legende par type present, sans collision."""
        used = sorted({kind for row in self._cells for kind in row if kind})
        assigned: dict[str, str] = {}
        taken: set[str] = {"."}
        for kind in used:  # d'abord les symboles habituels, s'ils sont libres
            wanted = self._symbols.get(kind, "")
            if wanted and wanted not in taken:
                assigned[kind] = wanted
                taken.add(wanted)
        for kind in used:
            if kind in assigned:
                continue
            symbol = palette.free_symbol(taken, kind.upper())
            assigned[kind] = symbol
            taken.add(symbol)
        self._symbols.update(assigned)
        return assigned
