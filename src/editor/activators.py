"""Plaques, boutons spectraux, et blocs qu'ils commandent, cote editeur.

Le jeu lit le champ `activators` du JSON (voir `world/level.py`). L'editeur
le conserve a cote de la grille : un activateur n'occupe pas une cellule, il
recouvre `width` tuiles et pointe vers des coordonnees `setBlock`. Chaque
cible a sa propre `action` (`hide`, `show`, `ignite`). `kind` vaut `plate`
(poids au sol) ou `spectral` (bouton F, duree). L'ancien champ `invert`
equivaut a `show` sur toutes les cibles sans `action`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import settings
from src.editor import palette
from src.world.mechanisms import (
    clamp_spectral_duration,
    cycle_link_action,
    default_link_action,
    parse_activator_kind,
    parse_link_action,
)


class ActivatorError(ValueError):
    """Entree `activators` illisible."""


ACTION_LABEL = {
    settings.LINK_ACTION_HIDE: "cache",
    settings.LINK_ACTION_SHOW: "montre",
    settings.LINK_ACTION_IGNITE: "allume",
}

KIND_LABEL = {
    settings.ACTIVATOR_KIND_PLATE: "sol",
    settings.ACTIVATOR_KIND_SPECTRAL: "esprit",
}


@dataclass(frozen=True, slots=True)
class LinkTarget:
    """Une cellule commandee, avec l'action a appliquer a l'activation."""

    column: int
    row: int
    action: str = settings.LINK_ACTION_HIDE

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", parse_link_action(self.action))

    @property
    def cell(self) -> tuple[int, int]:
        return self.column, self.row

    def with_action(self, action: str) -> "LinkTarget":
        return LinkTarget(self.column, self.row, action)

    def to_json(self) -> dict:
        return {
            "x": self.column,
            "y": self.row,
            "type": "void",
            "action": self.action,
        }


@dataclass(frozen=True, slots=True)
class Activator:
    """Un activateur : origine, largeur, cibles, kind plaque ou spectral."""

    column: int
    row: int
    width: int
    targets: tuple[LinkTarget, ...] = ()
    kind: str = settings.ACTIVATOR_KIND_PLATE
    duration: float = settings.SPECTRAL_BUTTON_DURATION

    def __post_init__(self) -> None:
        if self.width < 1:
            raise ValueError("width doit valoir au moins 1")
        if self.column < 0 or self.row < 0:
            raise ValueError("column et row doivent etre positifs")
        object.__setattr__(self, "kind", parse_activator_kind(self.kind))
        object.__setattr__(self, "duration", clamp_spectral_duration(self.duration))

    @property
    def last_column(self) -> int:
        return self.column + self.width - 1

    @property
    def is_spectral(self) -> bool:
        return self.kind == settings.ACTIVATOR_KIND_SPECTRAL

    def covers(self, column: int, row: int) -> bool:
        """Indique si la cellule appartient a l'activateur."""
        return self.row == row and self.column <= column <= self.last_column

    def has_target(self, column: int, row: int) -> bool:
        return any(target.column == column and target.row == row for target in self.targets)

    def target_at(self, column: int, row: int) -> LinkTarget | None:
        for target in self.targets:
            if target.column == column and target.row == row:
                return target
        return None

    def _copy(self, **changes) -> "Activator":
        return Activator(
            changes.get("column", self.column),
            changes.get("row", self.row),
            changes.get("width", self.width),
            changes.get("targets", self.targets),
            changes.get("kind", self.kind),
            changes.get("duration", self.duration),
        )

    def resized(self, column: int, width: int) -> "Activator":
        """Meme cibles, nouvelle emprise horizontale."""
        return self._copy(column=column, width=width)

    def with_toggled(self, column: int, row: int, cell_kind: str = "") -> "Activator":
        """Ajoute (action par defaut) ou retire la cellule des cibles."""
        existing = self.target_at(column, row)
        if existing is not None:
            return self._copy(
                targets=tuple(
                    target
                    for target in self.targets
                    if target.column != column or target.row != row
                )
            )
        added = LinkTarget(column, row, default_link_action(cell_kind))
        return self._copy(targets=(*self.targets, added))

    def with_target(self, target: LinkTarget) -> "Activator":
        """Remplace ou ajoute le lien de cette cellule."""
        kept = tuple(
            item
            for item in self.targets
            if item.column != target.column or item.row != target.row
        )
        return self._copy(targets=(*kept, target))

    def with_cycled_action(self, column: int, row: int, cell_kind: str) -> "Activator":
        """Passe a l'action suivante sur le lien existant."""
        current = self.target_at(column, row)
        if current is None:
            return self
        nxt = cycle_link_action(current.action, cell_kind)
        return self.with_target(current.with_action(nxt))

    def with_kind(self, kind: str) -> "Activator":
        return self._copy(kind=parse_activator_kind(kind))

    def with_duration(self, duration: float) -> "Activator":
        return self._copy(duration=clamp_spectral_duration(duration))

    def clipped(self, columns: int, rows: int) -> "Activator | None":
        """Recadre dans la carte, ou None si l'activateur est entierement dehors."""
        if self.row < 0 or self.row >= rows or self.column >= columns:
            return None
        column = max(0, self.column)
        width = min(self.width, columns - column)
        if width < 1:
            return None
        targets = tuple(
            target
            for target in self.targets
            if 0 <= target.column < columns and 0 <= target.row < rows
        )
        return self._copy(column=column, width=width, targets=targets)

    def to_json(self) -> dict:
        """Objet JSON attendu par `Level._parse_activator`."""
        payload: dict = {
            "x": self.column,
            "y": self.row,
            "width": self.width,
            "activate": {
                "setBlock": [target.to_json() for target in self.targets]
            },
        }
        if self.kind != settings.ACTIVATOR_KIND_PLATE:
            payload["kind"] = self.kind
        if self.kind == settings.ACTIVATOR_KIND_SPECTRAL:
            payload["duration"] = self.duration
        return payload


def can_link_kind(kind: str) -> bool:
    """Indique si ce type peut etre commande par un activateur.

    Le jeu relie le terrain, les murs spectraux, les blocs invisibles, les
    piques et les lance-flammes. Pas les items, ennemis, ni le decor.
    """
    if not kind:
        return False
    if kind in ("spectral_wall", "flamethrower", settings.TILE_KIND_HIDDEN):
        return True
    item = palette.item(kind)
    return item.is_terrain


def parse_activators(raw: object) -> tuple[Activator, ...]:
    """Lit le champ `activators` d'une carte, ou () s'il est absent."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ActivatorError("activators doit etre une liste")
    parsed: list[Activator] = []
    for index, entry in enumerate(raw):
        try:
            parsed.append(_parse_one(entry))
        except ActivatorError as error:
            raise ActivatorError(f"activators[{index}] : {error}") from error
        except ValueError as error:
            raise ActivatorError(f"activators[{index}] : {error}") from error
    return tuple(parsed)


def dump_activators(activators: Sequence[Activator]) -> list[dict]:
    """N'ecrit que les activateurs qui ont au moins une cible : le jeu l'exige."""
    return [activator.to_json() for activator in activators if activator.targets]


def cluster_targets(
    targets: Sequence[LinkTarget],
) -> tuple[tuple[float, float, str], ...]:
    """Centres de grille des groupes 4-connexes, un par action."""
    by_action: dict[str, set[tuple[int, int]]] = {}
    for target in targets:
        by_action.setdefault(target.action, set()).add(target.cell)
    centers: list[tuple[float, float, str]] = []
    for action, cells in by_action.items():
        remaining = set(cells)
        while remaining:
            seed = remaining.pop()
            stack = [seed]
            cluster = [seed]
            while stack:
                column, row = stack.pop()
                for next_column, next_row in (
                    (column + 1, row),
                    (column - 1, row),
                    (column, row + 1),
                    (column, row - 1),
                ):
                    neighbor = (next_column, next_row)
                    if neighbor not in remaining:
                        continue
                    remaining.remove(neighbor)
                    cluster.append(neighbor)
                    stack.append(neighbor)
            center_x = sum(column for column, _row in cluster) / len(cluster)
            center_y = sum(row for _column, row in cluster) / len(cluster)
            centers.append((center_x, center_y, action))
    return tuple(centers)


def activator_at(activators: Sequence[Activator], column: int, row: int) -> int | None:
    """Index de l'activateur qui couvre la cellule, ou None."""
    for index, activator in enumerate(activators):
        if activator.covers(column, row):
            return index
    return None


def overlaps_any(
    activators: Sequence[Activator],
    column: int,
    row: int,
    width: int,
    skip: int | None = None,
) -> int | None:
    """Index d'un activateur qui chevauche `[column, column+width)` sur `row`."""
    last = column + width - 1
    for index, activator in enumerate(activators):
        if skip is not None and index == skip:
            continue
        if activator.row != row:
            continue
        if activator.column <= last and column <= activator.last_column:
            return index
    return None


def prune(
    activators: Iterable[Activator],
    *,
    columns: int,
    rows: int,
    kind_at,
) -> tuple[Activator, ...]:
    """Retire les cibles vides / hors carte, recadre les activateurs."""
    kept: list[Activator] = []
    for activator in activators:
        clipped = activator.clipped(columns, rows)
        if clipped is None:
            continue
        targets = tuple(
            target
            for target in clipped.targets
            if can_link_kind(kind_at(target.column, target.row))
        )
        kept.append(clipped._copy(targets=targets))
    return tuple(kept)


def _parse_one(raw: object) -> Activator:
    if not isinstance(raw, dict):
        raise ActivatorError("doit etre un objet JSON")
    column = _coord(raw, "x", "x_activator", "x_Activator")
    row = _coord(raw, "y", "y_activator", "y_Activator")
    width = int(raw.get("width", 1))
    if width < 1:
        raise ActivatorError("width doit etre un entier >= 1")
    try:
        kind = parse_activator_kind(raw.get("kind"))
    except ValueError as error:
        raise ActivatorError(str(error)) from error
    duration = settings.SPECTRAL_BUTTON_DURATION
    if "duration" in raw:
        value = raw["duration"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ActivatorError("duration doit etre un nombre")
        duration = clamp_spectral_duration(float(value))
    default_action = (
        settings.LINK_ACTION_SHOW
        if _parse_invert(raw)
        else settings.LINK_ACTION_HIDE
    )
    targets = _parse_set_blocks(raw.get("activate"), default_action=default_action)
    return Activator(column, row, width, tuple(targets), kind, duration)


def _parse_set_blocks(activate: object, *, default_action: str) -> list[LinkTarget]:
    if activate is None:
        raise ActivatorError("activate est requis")
    if not isinstance(activate, dict):
        raise ActivatorError("activate doit etre un objet { setBlock: ... }")
    if "setBlock" not in activate:
        raise ActivatorError("activate.setBlock est requis")
    block = activate["setBlock"]
    if isinstance(block, dict):
        entries = [block]
    elif isinstance(block, list):
        entries = block
    else:
        raise ActivatorError("setBlock doit etre un objet ou une liste d'objets")
    tiles: list[LinkTarget] = []
    seen: set[tuple[int, int]] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ActivatorError(f"setBlock[{index}] doit etre un objet")
        kind = entry.get("type", "void")
        if kind != "void":
            raise ActivatorError(f"setBlock type '{kind}' non supporte (uniquement 'void')")
        cell = (_coord(entry, "x"), _coord(entry, "y"))
        if cell in seen:
            continue
        seen.add(cell)
        try:
            action = parse_link_action(entry.get("action"), default_action)
        except ValueError as error:
            raise ActivatorError(f"setBlock[{index}] : {error}") from error
        tiles.append(LinkTarget(cell[0], cell[1], action))
    return tiles


def _coord(raw: dict, *keys: str) -> int:
    for key in keys:
        if key in raw:
            return _as_int(raw[key], key)
    raise ActivatorError(f"champ manquant ({', '.join(keys)})")


def _parse_invert(raw: dict) -> bool:
    if "invert" not in raw:
        return False
    value = raw["invert"]
    if not isinstance(value, bool):
        raise ActivatorError("invert doit etre un booleen")
    return value


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ActivatorError(f"{name} doit etre un entier")
    return value
