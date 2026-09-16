"""Plaques de pression et blocs qu'elles commandent, cote editeur.

Le jeu lit le champ `activators` du JSON (voir `world/level.py`). L'editeur
le conserve a cote de la grille : une plaque n'occupe pas une cellule, elle
recouvre `width` tuiles et pointe vers des coordonnees `setBlock type=void`.
`invert` (optionnel) fait apparaitre les blocs a l'activation au lieu de
les retirer.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.editor import palette


class ActivatorError(ValueError):
    """Entree `activators` illisible."""


@dataclass(frozen=True, slots=True)
class Activator:
    """Une plaque : origine (colonne, ligne), largeur en tuiles, cibles void."""

    column: int
    row: int
    width: int
    targets: tuple[tuple[int, int], ...] = ()
    inverted: bool = False

    def __post_init__(self) -> None:
        if self.width < 1:
            raise ValueError("width doit valoir au moins 1")
        if self.column < 0 or self.row < 0:
            raise ValueError("column et row doivent etre positifs")

    @property
    def last_column(self) -> int:
        return self.column + self.width - 1

    def covers(self, column: int, row: int) -> bool:
        """Indique si la cellule appartient a la plaque."""
        return self.row == row and self.column <= column <= self.last_column

    def has_target(self, column: int, row: int) -> bool:
        return (column, row) in self.targets

    def resized(self, column: int, width: int) -> "Activator":
        """Meme cibles, nouvelle emprise horizontale."""
        return Activator(column, self.row, width, self.targets, self.inverted)

    def with_toggled(self, column: int, row: int) -> "Activator":
        """Ajoute ou retire la cellule des cibles, sans doublon."""
        cell = (column, row)
        if cell in self.targets:
            return Activator(
                self.column,
                self.row,
                self.width,
                tuple(target for target in self.targets if target != cell),
                self.inverted,
            )
        return Activator(
            self.column,
            self.row,
            self.width,
            (*self.targets, cell),
            self.inverted,
        )

    def with_inverted(self, inverted: bool) -> "Activator":
        """Meme cibles, sens cache / montre inverse."""
        return Activator(self.column, self.row, self.width, self.targets, inverted)

    def clipped(self, columns: int, rows: int) -> "Activator | None":
        """Recadre dans la carte, ou None si la plaque est entierement dehors."""
        if self.row < 0 or self.row >= rows or self.column >= columns:
            return None
        column = max(0, self.column)
        width = min(self.width, columns - column)
        if width < 1:
            return None
        targets = tuple(
            (target_column, target_row)
            for target_column, target_row in self.targets
            if 0 <= target_column < columns and 0 <= target_row < rows
        )
        return Activator(column, self.row, width, targets, self.inverted)

    def to_json(self) -> dict:
        """Objet JSON attendu par `Level._parse_activator`."""
        payload: dict = {
            "x": self.column,
            "y": self.row,
            "width": self.width,
            "activate": {
                "setBlock": [
                    {"x": column, "y": row, "type": "void"}
                    for column, row in self.targets
                ]
            },
        }
        if self.inverted:
            payload["invert"] = True
        return payload


def can_link_kind(kind: str) -> bool:
    """Indique si ce type peut disparaitre sous une plaque (`setBlock void`).

    Le jeu ne relie que le terrain, les murs spectraux et les piques
    (`walls`, `spectral_walls`, `hazards`). Pas les items ni le decor.
    """
    if not kind:
        return False
    item = palette.item(kind)
    return item.is_terrain or kind == "spectral_wall"


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
    return tuple(parsed)


def dump_activators(activators: Sequence[Activator]) -> list[dict]:
    """N'ecrit que les plaques qui ont au moins une cible : le jeu l'exige."""
    return [activator.to_json() for activator in activators if activator.targets]


def cluster_targets(cells: Sequence[tuple[int, int]]) -> tuple[tuple[float, float], ...]:
    """Centres de grille des groupes 4-connexes (un lien par paquet, pas par tuile)."""
    remaining = set(cells)
    centers: list[tuple[float, float]] = []
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
        centers.append((center_x, center_y))
    return tuple(centers)


def activator_at(activators: Sequence[Activator], column: int, row: int) -> int | None:
    """Index de la plaque qui couvre la cellule, ou None."""
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
    """Index d'une plaque qui chevauche `[column, column+width)` sur `row`."""
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
    """Retire les cibles vides / hors carte, recadre les plaques."""
    kept: list[Activator] = []
    for activator in activators:
        clipped = activator.clipped(columns, rows)
        if clipped is None:
            continue
        targets = tuple(
            cell
            for cell in clipped.targets
            if can_link_kind(kind_at(*cell))
        )
        kept.append(
            Activator(
                clipped.column,
                clipped.row,
                clipped.width,
                targets,
                clipped.inverted,
            )
        )
    return tuple(kept)


def _parse_one(raw: object) -> Activator:
    if not isinstance(raw, dict):
        raise ActivatorError("doit etre un objet JSON")
    column = _coord(raw, "x", "x_activator", "x_Activator")
    row = _coord(raw, "y", "y_activator", "y_Activator")
    width = int(raw.get("width", 1))
    if width < 1:
        raise ActivatorError("width doit etre un entier >= 1")
    targets = _parse_set_blocks(raw.get("activate"))
    return Activator(column, row, width, tuple(targets), _parse_invert(raw))


def _parse_set_blocks(activate: object) -> list[tuple[int, int]]:
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
    tiles: list[tuple[int, int]] = []
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
        tiles.append(cell)
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
