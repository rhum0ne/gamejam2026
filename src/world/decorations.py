"""Decors sans collision poses dans le niveau (coffres, panneaux, lampes...).

Purement visuel : ces sprites n'entrent jamais dans les listes solides du
moteur de physique (`Level.solid_platforms` / `Level.static_walls`), a la
difference des tuiles de `obstacles.py`. Le pattern reprend celui de
`obstacles.Torch` : une texture chargee une fois via `ui/sprites.py`, posee
au sol de sa tuile.

Ajouter un type de decoration : une entree dans `DECORATION_SPECS` (planche,
rectangle en pixels, taille affichee) suffit, `world/level.py` s'en sert pour
generer la fabrique et l'editeur pour peupler sa palette.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import arcade

import settings
from src.ui import sprites


@dataclass(frozen=True, slots=True)
class DecorationSpec:
    """Description d'un type de decoration choisi dans la legende d'une carte."""

    sheet: Path
    box: tuple[int, int, int, int]  # (left, top, right, bottom), en pixels dans la planche
    display_size: int  # largeur affichee en jeu (px) ; la hauteur suit le ratio d'origine


DECORATION_SPECS: dict[str, DecorationSpec] = {
    "chest": DecorationSpec(
        sheet=settings.DECORATION_CHEST_SHEET,
        box=settings.DECORATION_CHEST_BOX,
        display_size=settings.DECORATION_CHEST_SIZE,
    ),
    "sign": DecorationSpec(
        sheet=settings.DECORATION_SIGN_SHEET,
        box=settings.DECORATION_SIGN_BOX,
        display_size=settings.DECORATION_SIGN_SIZE,
    ),
    "lamp": DecorationSpec(
        sheet=settings.DECORATION_LAMP_SHEET,
        box=settings.DECORATION_LAMP_BOX,
        display_size=settings.DECORATION_LAMP_SIZE,
    ),
}


def decoration_spec(name: str) -> DecorationSpec:
    """Retourne la spec d'une decoration, ou leve ValueError."""
    if not name:
        raise ValueError("name ne doit pas etre vide")
    spec = DECORATION_SPECS.get(name)
    if spec is None:
        raise ValueError(f"decoration inconnue : '{name}'")
    return spec


def decoration_kinds() -> tuple[str, ...]:
    """Types de decoration disponibles (cles de `DECORATION_SPECS`)."""
    return tuple(DECORATION_SPECS)


class Decoration(arcade.Sprite):
    """Element de decor pose au sol de sa tuile : jamais solide, jamais mis a jour.

    Contrairement a `obstacles.Wall`, la texture garde ses proportions
    d'origine (les planches de decor ne sont pas des tuiles carrees de
    `TILE_SIZE`) : `display_size` en fixe la largeur affichee, la base du
    sprite est alignee sur le bas de la tuile plutot que son centre (comme
    `obstacles.Torch`), pour que l'objet ait l'air pose sur le sol.
    """

    def __init__(self, kind: str, center_x: float, center_y: float) -> None:
        spec = decoration_spec(kind)
        texture = sprites.load_sheet_region(spec.sheet, spec.box)
        scale = spec.display_size / texture.width
        tile_bottom = center_y - settings.TILE_SIZE / 2
        super().__init__(
            texture,
            scale=scale,
            center_x=center_x,
            center_y=tile_bottom + texture.height * scale / 2,
        )
        self.kind = kind
