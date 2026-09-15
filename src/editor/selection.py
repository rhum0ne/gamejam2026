"""Rectangle de selection et bloc de presse-papiers, en coordonnees de grille.

Convention de coordonnees de l'editeur, identique au JSON : la colonne 0 est a
gauche, la **ligne 0 est en haut** (`rows[0]` est la ligne la plus haute de la
carte). La conversion vers les coordonnees monde d'Arcade (y vers le haut) est
faite au dernier moment, dans `canvas.py`.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GridRect:
    """Zone rectangulaire de cellules, bornes incluses."""

    min_column: int
    min_row: int
    max_column: int
    max_row: int

    @classmethod
    def from_corners(cls, first: tuple[int, int], second: tuple[int, int]) -> "GridRect":
        """Rectangle defini par deux cellules quelconques (glisser-deposer)."""
        column_a, row_a = first
        column_b, row_b = second
        return cls(
            min(column_a, column_b),
            min(row_a, row_b),
            max(column_a, column_b),
            max(row_a, row_b),
        )

    @classmethod
    def whole(cls, columns: int, rows: int) -> "GridRect":
        if columns < 1 or rows < 1:
            raise ValueError("columns et rows doivent valoir au moins 1")
        return cls(0, 0, columns - 1, rows - 1)

    @property
    def width(self) -> int:
        return self.max_column - self.min_column + 1

    @property
    def height(self) -> int:
        return self.max_row - self.min_row + 1

    @property
    def count(self) -> int:
        return self.width * self.height

    def contains(self, column: int, row: int) -> bool:
        return (
            self.min_column <= column <= self.max_column
            and self.min_row <= row <= self.max_row
        )

    def cells(self) -> Iterator[tuple[int, int]]:
        """Parcourt les cellules de haut en bas, de gauche a droite."""
        for row in range(self.min_row, self.max_row + 1):
            for column in range(self.min_column, self.max_column + 1):
                yield column, row

    def clamped(self, columns: int, rows: int) -> "GridRect | None":
        """Recadre le rectangle dans la carte, ou None s'il est entierement dehors."""
        min_column = max(0, self.min_column)
        min_row = max(0, self.min_row)
        max_column = min(columns - 1, self.max_column)
        max_row = min(rows - 1, self.max_row)
        if min_column > max_column or min_row > max_row:
            return None
        return GridRect(min_column, min_row, max_column, max_row)


@dataclass(frozen=True, slots=True)
class Block:
    """Bloc de cellules copie : `cells[0]` est la ligne du haut."""

    cells: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.cells or not self.cells[0]:
            raise ValueError("un bloc copie ne peut pas etre vide")
        widths = {len(row) for row in self.cells}
        if len(widths) != 1:
            raise ValueError("toutes les lignes d'un bloc doivent avoir la meme largeur")

    @classmethod
    def from_rows(cls, rows: Sequence[Sequence[str]]) -> "Block":
        return cls(tuple(tuple(row) for row in rows))

    @property
    def width(self) -> int:
        return len(self.cells[0])

    @property
    def height(self) -> int:
        return len(self.cells)

    def rect_at(self, column: int, row: int) -> GridRect:
        """Zone couverte si le bloc est colle avec son coin haut-gauche ici."""
        return GridRect(column, row, column + self.width - 1, row + self.height - 1)
