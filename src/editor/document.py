"""Carte en cours d'edition : grille de types, metadonnees, lecture/ecriture JSON.

Le document ne manipule **pas** de symboles : chaque cellule contient le nom du
type (`"wall"`, `"enemy"`, `""` pour du vide). Les symboles de legende ne sont
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
from src.editor.activators import (
    Activator,
    ActivatorError,
    can_link_kind,
    dump_activators,
    parse_activators,
    prune,
)
from src.editor.history import CellChange, Edit, GridState, History
from src.editor.selection import Block, GridRect
from src.world.falling_block import FallingSpec, dump_falling_specs, parse_falling_specs
from src.world.flamethrower import FlameSpec, dump_flame_specs, parse_flame_specs
from src.world.spring import SpringSpec, dump_spring_specs, parse_spring_specs
from src.world.themes import normalize_theme, parse_theme

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
        activators: Sequence[Activator] = (),
        flames: dict[tuple[int, int], FlameSpec] | None = None,
        fallings: dict[tuple[int, int], FallingSpec] | None = None,
        springs: dict[tuple[int, int], SpringSpec] | None = None,
        theme: str = settings.GROUND_THEME_DEFAULT,
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
        self.theme = normalize_theme(theme)
        self.path = path
        self.history = History()
        self._cells: list[list[str]] = [list(row) for row in cells]
        self._symbols: dict[str, str] = dict(palette.preferred_symbols())
        if symbols:
            self._symbols.update(symbols)
        self._version = 0
        self._layout_version = 0
        self._saved_version = 0
        self._activators: tuple[Activator, ...] = tuple(activators)
        self._flames: dict[tuple[int, int], FlameSpec] = dict(flames or {})
        self._flame_brush = FlameSpec(0, 0)
        self._fallings: dict[tuple[int, int], FallingSpec] = dict(fallings or {})
        self._falling_brush = FallingSpec(0, 0)
        self._springs: dict[tuple[int, int], SpringSpec] = dict(springs or {})
        self._spring_brush = SpringSpec(0, 0)
        self._stroke: list[CellChange] | None = None
        self._stroke_label = ""
        self._stroke_activators: tuple[Activator, ...] | None = None
        self._sync_flames()
        self._sync_fallings()
        self._sync_springs()

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
        """Carte vide, entouree d'un cadre de terre pour ne pas tomber hors monde."""
        columns = max(settings.EDITOR_MIN_COLUMNS, min(settings.EDITOR_MAX_COLUMNS, columns))
        rows = max(settings.EDITOR_MIN_ROWS, min(settings.EDITOR_MAX_ROWS, rows))
        cells = [[palette.EMPTY] * columns for _ in range(rows)]
        for column in range(columns):
            cells[0][column] = "wall"
            cells[rows - 1][column] = "bedrock"
        for row in range(rows):
            cells[row][0] = "wall"
            cells[row][columns - 1] = "wall"
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
        try:
            activators = parse_activators(data.get("activators"))
        except ActivatorError as error:
            raise DocumentError(str(error)) from error
        try:
            flames = parse_flame_specs(data.get("flamethrowers"))
        except ValueError as error:
            raise DocumentError(str(error)) from error
        try:
            fallings = parse_falling_specs(data.get("falling_blocks"))
        except ValueError as error:
            raise DocumentError(str(error)) from error
        try:
            springs = parse_spring_specs(data.get("springs"))
        except ValueError as error:
            raise DocumentError(str(error)) from error
        try:
            theme = parse_theme(data.get("theme"))
        except (TypeError, ValueError) as error:
            raise DocumentError(str(error)) from error
        return cls(
            name=str(data.get("name", "Niveau sans nom")),
            hint=str(data.get("hint", "")),
            tile_size=int(data.get("tile_size", settings.TILE_SIZE)),
            cells=cells,
            path=path,
            symbols=symbols,
            activators=activators,
            flames=flames,
            fallings=fallings,
            springs=springs,
            theme=theme,
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

    @property
    def activators(self) -> tuple[Activator, ...]:
        return self._activators

    def flame_at(self, column: int, row: int) -> FlameSpec | None:
        """Reglages du lance-flammes pose en (colonne, ligne), s'il y en a un."""
        return self._flames.get((column, row))

    def adjust_flame(
        self,
        column: int,
        row: int,
        *,
        range_delta: int = 0,
        interval_delta: float = 0.0,
        rotate: bool = False,
    ) -> FlameSpec | None:
        """Modifie le lance-flammes sous le curseur. None si la cellule n'en est pas un."""
        if self.cell(column, row) != "flamethrower":
            return None
        current = self._flames.get((column, row)) or FlameSpec(column, row)
        updated = current
        if range_delta:
            updated = updated.with_range(updated.range_tiles + range_delta)
        if interval_delta:
            updated = updated.with_interval(updated.interval + interval_delta)
        if rotate:
            updated = updated.rotated()
        if updated == current:
            return current
        self._flames[(column, row)] = updated
        self._flame_brush = FlameSpec(
            0, 0, updated.range_tiles, updated.interval, updated.direction
        )
        self._version += 1
        return updated

    def falling_at(self, column: int, row: int) -> FallingSpec | None:
        """Reglages du bloc tombant pose en (colonne, ligne), s'il y en a un."""
        return self._fallings.get((column, row))

    def falling_specs(self) -> tuple[FallingSpec, ...]:
        """Tous les blocs tombants poses, pour le rendu de l'editeur."""
        return tuple(self._fallings.values())

    def adjust_falling(
        self,
        column: int,
        row: int,
        *,
        delay_delta: float = 0.0,
        respawn_delta: float = 0.0,
        invert_ghost: bool = False,
    ) -> FallingSpec | None:
        """Modifie le bloc tombant sous le curseur. None si la cellule n'en est pas un."""
        if self.cell(column, row) != settings.TILE_KIND_FALLING:
            return None
        current = self._fallings.get((column, row)) or FallingSpec(column, row)
        updated = current
        if delay_delta:
            updated = updated.with_delay(updated.delay + delay_delta)
        if respawn_delta:
            updated = updated.with_respawn(updated.respawn + respawn_delta)
        if invert_ghost:
            updated = updated.with_ghost_only(not updated.ghost_only)
        if updated == current:
            return current
        self._fallings[(column, row)] = updated
        self._falling_brush = FallingSpec(
            0, 0, updated.delay, updated.respawn, updated.ghost_only
        )
        self._version += 1
        return updated

    def spring_at(self, column: int, row: int) -> SpringSpec | None:
        """Orientation du ressort pose en (colonne, ligne), s'il y en a un."""
        return self._springs.get((column, row))

    def adjust_spring(self, column: int, row: int, *, rotate: bool = False) -> SpringSpec | None:
        """Tourne le ressort sous le curseur. None si la cellule n'en est pas un."""
        if self.cell(column, row) != settings.TILE_KIND_SPRING:
            return None
        current = self._springs.get((column, row)) or SpringSpec(column, row)
        updated = current.rotated() if rotate else current
        if updated == current:
            return current
        self._springs[(column, row)] = updated
        self._spring_brush = SpringSpec(0, 0, updated.direction)
        self._version += 1
        return updated

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
        for index, activator in enumerate(self._activators, start=1):
            if not activator.targets:
                issues.append(f"plaque {index} sans bloc lie (le jeu refusera la carte)")
                continue
            missing = [
                f"{target.column},{target.row}"
                for target in activator.targets
                if not can_link_kind(self.cell(target.column, target.row))
            ]
            if missing:
                issues.append(
                    f"plaque {index} : cibles vides ou invalides ({', '.join(missing[:4])})"
                )
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
            self._stroke_activators = self._activators

    def end_stroke(self) -> None:
        """Ferme le groupe ouvert par `begin_stroke` et l'empile s'il a servi."""
        pending = self._stroke
        before_activators = self._stroke_activators
        self._stroke = None
        self._stroke_activators = None
        if pending is None:
            return
        self._sync_activators()
        after_activators = self._activators
        retargets = before_activators != after_activators
        if not pending and not retargets:
            return
        self.history.push(
            Edit(
                label=self._stroke_label,
                changes=tuple(pending),
                activators_before=before_activators if retargets else None,
                activators_after=after_activators if retargets else None,
            )
        )

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
        before_activators = self._activators
        self._sync_activators()
        after_activators = self._activators
        retargets = before_activators != after_activators
        self.history.push(
            Edit(
                label="redimensionner",
                before=before,
                after=after,
                activators_before=before_activators if retargets else None,
                activators_after=after_activators if retargets else None,
            )
        )
        self._version += 1
        self._layout_version += 1
        self._sync_flames()
        self._sync_fallings()
        self._sync_springs()
        return True

    def can_link(self, column: int, row: int) -> bool:
        """Indique si la cellule peut etre une cible `setBlock void`."""
        return self.inside(column, row) and can_link_kind(self.cell(column, row))

    def add_activator(
        self,
        column: int,
        row: int,
        width: int,
        *,
        kind: str = settings.ACTIVATOR_KIND_PLATE,
    ) -> int:
        """Ajoute un activateur vide et retourne son index."""
        if not self.inside(column, row) or not self.inside(column + width - 1, row):
            raise ValueError("la plaque sort de la carte")
        before = self._activators
        added = Activator(column, row, width, kind=kind)
        self._activators = (*before, added)
        self._commit_activators("placer une plaque", before)
        return len(self._activators) - 1

    def remove_activator(self, index: int) -> None:
        """Supprime une plaque. Leve IndexError si l'index est hors liste."""
        before = self._activators
        self._activators = tuple(item for i, item in enumerate(before) if i != index)
        if self._activators == before:
            raise IndexError("index de plaque inconnu")
        self._commit_activators("supprimer une plaque", before)

    def replace_activator(self, index: int, activator: Activator, label: str) -> None:
        """Remplace une plaque (redimensionnement, cibles)."""
        if index < 0 or index >= len(self._activators):
            raise IndexError("index de plaque inconnu")
        if self._activators[index] == activator:
            return
        before = self._activators
        updated = list(before)
        updated[index] = activator
        self._activators = tuple(updated)
        self._commit_activators(label, before)

    def toggle_target(self, index: int, column: int, row: int) -> bool:
        """Ajoute ou retire une cible. Retourne True si le lien est maintenant actif."""
        if not self.can_link(column, row):
            return False
        current = self._activators[index]
        updated = current.with_toggled(column, row, self.cell(column, row))
        added = updated.has_target(column, row)
        self.replace_activator(index, updated, "lier un bloc" if added else "delier un bloc")
        return added

    def cycle_target_action(self, index: int, column: int, row: int) -> str | None:
        """Passe a l'action suivante du lien. None si la cellule n'est pas liee."""
        current = self._activators[index]
        if not current.has_target(column, row):
            return None
        updated = current.with_cycled_action(column, row, self.cell(column, row))
        target = updated.target_at(column, row)
        if target is None:
            return None
        self.replace_activator(index, updated, "changer l'action d'un lien")
        return target.action

    def toggle_activator_kind(self, index: int) -> str:
        """Alterne plaque au sol / bouton spectral. Retourne le nouveau kind."""
        current = self._activators[index]
        nxt = (
            settings.ACTIVATOR_KIND_SPECTRAL
            if current.kind == settings.ACTIVATOR_KIND_PLATE
            else settings.ACTIVATOR_KIND_PLATE
        )
        updated = current.with_kind(nxt)
        self.replace_activator(index, updated, "changer le type d'activateur")
        return updated.kind

    def adjust_activator_duration(self, index: int, delta: float) -> float:
        """Change la duree d'un bouton spectral. Retourne la nouvelle valeur."""
        current = self._activators[index]
        updated = current.with_duration(current.duration + delta)
        if updated == current:
            return current.duration
        self.replace_activator(index, updated, "regler la duree d'un bouton")
        return updated.duration

    def set_metadata(
        self,
        *,
        name: str | None = None,
        hint: str | None = None,
        tile_size: int | None = None,
        theme: str | None = None,
    ) -> None:
        """Change le nom, l'indice, la taille de tuile ou le theme (hors historique)."""
        if name is not None:
            self.name = name
        if hint is not None:
            self.hint = hint
        if tile_size is not None:
            if tile_size <= 0:
                raise ValueError("tile_size doit etre strictement positif")
            self.tile_size = tile_size
            self._layout_version += 1
        if theme is not None:
            self.theme = normalize_theme(theme)
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
        payload = {
            "name": self.name,
            "hint": self.hint,
            "tile_size": self.tile_size,
            "legend": legend,
            "rows": rows,
        }
        if self.theme != settings.GROUND_THEME_DEFAULT:
            payload["theme"] = self.theme
        activators = dump_activators(self._activators)
        if activators:
            payload["activators"] = activators
        flames = dump_flame_specs(self._flames)
        if flames:
            payload["flamethrowers"] = flames
        fallings = dump_falling_specs(self._fallings)
        if fallings:
            payload["falling_blocks"] = fallings
        springs = dump_spring_specs(self._springs)
        if springs:
            payload["springs"] = springs
        return payload

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
        before_activators = self._activators
        self._sync_activators()
        after_activators = self._activators
        retargets = before_activators != after_activators
        if self._stroke is not None:
            self._stroke.extend(changes)
        else:
            self.history.push(
                Edit(
                    label=label,
                    changes=tuple(changes),
                    activators_before=before_activators if retargets else None,
                    activators_after=after_activators if retargets else None,
                )
            )
        self._version += 1
        self._sync_flames()
        self._sync_fallings()
        self._sync_springs()
        return tuple((change.column, change.row, change.after) for change in changes)

    def _sync_activators(self) -> None:
        """Recadre les plaques et lache les cibles qui ne sont plus des blocs."""
        self._activators = prune(
            self._activators,
            columns=self.columns,
            rows=self.rows,
            kind_at=self.cell,
        )

    def _sync_flames(self) -> None:
        """Garde un spec par cellule `flamethrower`, jette le reste."""
        kept: dict[tuple[int, int], FlameSpec] = {}
        brush = self._flame_brush
        for row, line in enumerate(self._cells):
            for column, kind in enumerate(line):
                if kind != "flamethrower":
                    continue
                existing = self._flames.get((column, row))
                if existing is not None:
                    kept[(column, row)] = existing
                    continue
                kept[(column, row)] = FlameSpec(
                    column,
                    row,
                    brush.range_tiles,
                    brush.interval,
                    brush.direction,
                )
        self._flames = kept

    def _sync_fallings(self) -> None:
        """Garde un spec par cellule `falling_block`, jette le reste."""
        kept: dict[tuple[int, int], FallingSpec] = {}
        brush = self._falling_brush
        kind_name = settings.TILE_KIND_FALLING
        for row, line in enumerate(self._cells):
            for column, kind in enumerate(line):
                if kind != kind_name:
                    continue
                existing = self._fallings.get((column, row))
                if existing is not None:
                    kept[(column, row)] = existing
                    continue
                kept[(column, row)] = FallingSpec(
                    column,
                    row,
                    brush.delay,
                    brush.respawn,
                    brush.ghost_only,
                )
        self._fallings = kept

    def _sync_springs(self) -> None:
        """Garde un spec par cellule `spring`, jette le reste."""
        kept: dict[tuple[int, int], SpringSpec] = {}
        brush = self._spring_brush
        kind_name = settings.TILE_KIND_SPRING
        for row, line in enumerate(self._cells):
            for column, kind in enumerate(line):
                if kind != kind_name:
                    continue
                existing = self._springs.get((column, row))
                if existing is not None:
                    kept[(column, row)] = existing
                    continue
                kept[(column, row)] = SpringSpec(column, row, brush.direction)
        self._springs = kept

    def _commit_activators(self, label: str, before: tuple[Activator, ...]) -> None:
        if before == self._activators:
            return
        self.history.push(
            Edit(
                label=label,
                activators_before=before,
                activators_after=self._activators,
            )
        )
        self._version += 1

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
        states: tuple[CellState, ...] = ()
        if edit.reshapes:
            state = edit.after if forward else edit.before
            assert state is not None  # garanti par Edit.reshapes
            self._cells = [list(row) for row in state.cells]
            self._layout_version += 1
        else:
            replayed: list[CellState] = []
            for change in edit.changes:
                value = change.after if forward else change.before
                self._cells[change.row][change.column] = value
                replayed.append((change.column, change.row, value))
            states = tuple(replayed)
        if edit.retargets:
            restored = edit.activators_after if forward else edit.activators_before
            assert restored is not None
            self._activators = restored
        self._sync_flames()
        self._sync_fallings()
        self._sync_springs()
        return states

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
