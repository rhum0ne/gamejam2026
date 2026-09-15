"""Cache d'objets `arcade.Text`, partage par les ecrans hors-jeu et l'editeur.

Arcade emet un `PerformanceWarning` a chaque `arcade.draw_text` dans une boucle
de rendu : il faut reutiliser des objets `Text`. Deux facons de faire ici :

    - `label(...)` : cache par contenu et position, pour du texte statique
      (menus, aides). Le cache est borne et se vide d'un coup s'il deborde ;
    - `Line` : un `Text` possede par l'appelant, dont le contenu et la position
      changent a chaque frame (barres d'etat, valeurs qui defilent).
"""

from __future__ import annotations

import arcade

import settings
from src.ui.fonts import PIXEL_FONT

_CACHE: dict[tuple, arcade.Text] = {}
_CACHE_LIMIT = 512


def label(
    text: str,
    x: float,
    y: float,
    size: float,
    color: tuple[int, int, int] | tuple[int, int, int, int],
    anchor_x: str = "left",
    anchor_y: str = "baseline",
) -> arcade.Text:
    """Retourne un `Text` reutilisable pour ce libelle a cette position."""
    key = (text, round(x), round(y), size, color, anchor_x, anchor_y)
    cached = _CACHE.get(key)
    if cached is None:
        if len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.clear()
        cached = arcade.Text(
            text,
            x,
            y,
            color,
            font_size=size,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            font_name=PIXEL_FONT,
        )
        _CACHE[key] = cached
    return cached


def draw(
    text: str,
    x: float,
    y: float,
    size: float = settings.EDITOR_TEXT_SIZE,
    color: tuple[int, int, int] | tuple[int, int, int, int] = settings.COLOR_EDITOR_TEXT,
    anchor_x: str = "left",
    anchor_y: str = "baseline",
) -> None:
    """Raccourci : recupere le libelle en cache et le dessine."""
    label(text, x, y, size, color, anchor_x, anchor_y).draw()


class Line:
    """Ligne de texte mutable : le contenu et la position changent sans recreer l'objet."""

    def __init__(
        self,
        size: float = settings.EDITOR_TEXT_SIZE,
        color: tuple[int, int, int] | tuple[int, int, int, int] = settings.COLOR_EDITOR_TEXT,
        anchor_x: str = "left",
        anchor_y: str = "baseline",
    ) -> None:
        self._text = arcade.Text(
            "",
            0,
            0,
            color,
            font_size=size,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            font_name=PIXEL_FONT,
        )

    def draw(
        self,
        text: str,
        x: float,
        y: float,
        color: tuple[int, int, int] | tuple[int, int, int, int] | None = None,
    ) -> None:
        """Met a jour le contenu, la position, la couleur, puis dessine."""
        self._text.text = text
        self._text.x = x
        self._text.y = y
        if color is not None:
            self._text.color = color
        self._text.draw()
