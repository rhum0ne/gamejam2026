"""Cache d'objets `arcade.Text`, partage par les ecrans hors-jeu et l'editeur.

Arcade emet un `PerformanceWarning` a chaque `arcade.draw_text` dans une boucle
de rendu : il faut reutiliser des objets `Text`. Deux facons de faire ici :

    - `label(...)` : cache par contenu et position, pour du texte statique
      (menus, aides). Le cache est borne et se vide d'un coup s'il deborde ;
    - `Line` : un `Text` possede par l'appelant, dont le contenu et la position
      changent a chaque frame (barres d'etat, valeurs qui defilent).
"""

from __future__ import annotations

import time

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
        font_name: str | tuple[str, ...] | None = None,
    ) -> None:
        self._text = arcade.Text(
            "",
            0,
            0,
            color,
            font_size=size,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            font_name=font_name if font_name is not None else PIXEL_FONT,
        )

    def draw(
        self,
        text: str,
        x: float,
        y: float,
        color: tuple[int, int, int] | tuple[int, int, int, int] | None = None,
        *,
        max_width: float | None = None,
        overflow: str = "marquee",
    ) -> None:
        """Met a jour le contenu, la position, la couleur, puis dessine.

        Si `max_width` est fourni et que le texte depasse :
            - `marquee` : defilement horizontal ping-pong ;
            - `end` : aligne la fin (curseur de saisie toujours visible) ;
            - `clip` : coupe net a droite, sans defilement.
        """
        self._text.text = text
        self._text.y = y
        if color is not None:
            self._text.color = color
        if max_width is None or max_width <= 0:
            self._text.x = x
            self._text.draw()
            return
        width = float(self._text.content_width)
        if width <= max_width:
            self._text.x = x
            self._text.draw()
            return
        height = max(self._text.content_height, self._text.font_size) + 10
        if overflow == "clip":
            self._text.x = x
            with _clip(x, y - 6, max_width, height):
                self._text.draw()
            return
        overflow_px = width - max_width
        if overflow == "end":
            offset = overflow_px
        else:
            offset = _marquee_offset(overflow_px)
        # Fenetre de caracteres : le glyphe ne part jamais loin a gauche de `x`.
        # Le scissor coupe le reliquat (fraction de glyphe + bord droit).
        char_w = width / max(1, len(text))
        start = min(len(text) - 1, max(0, int(offset / char_w)))
        frac = offset - start * char_w
        visible = max(1, int(max_width / char_w) + 2)
        self._text.text = text[start : start + visible]
        self._text.x = x - frac
        with _clip(x, y - 6, max_width, height):
            self._text.draw()


class _clip:
    """Scissor OpenGL en coordonnees fenetre : coupe le texte qui debord.

    Assigner `camera.scissor` sans `use()` ne change rien. On ecrit donc
    directement `ctx.scissor` (le setter convertit deja les points Retina).
    """

    def __init__(self, x: float, y: float, width: float, height: float) -> None:
        self._box = (
            int(x),
            int(y),
            max(1, int(width)),
            max(1, int(height)),
        )
        self._window = None
        self._previous = None

    def __enter__(self) -> None:
        window = arcade.get_window()
        self._window = window
        self._previous = window.ctx.scissor
        window.ctx.scissor = self._box

    def __exit__(self, *_exc) -> None:
        window = self._window
        if window is not None:
            window.ctx.scissor = self._previous

    def __exit__(self, *_exc) -> None:
        window = self._window
        if window is not None:
            window.ctx.scissor = self._previous


def _marquee_offset(overflow: float) -> float:
    """Aller-retour : pause, glisse, pause, revient."""
    speed = settings.EDITOR_MARQUEE_SPEED
    pause = settings.EDITOR_MARQUEE_PAUSE
    travel = overflow / max(1.0, speed)
    period = travel + pause * 2
    loop = max(0.001, period * 2)
    cursor = time.perf_counter() % loop
    if cursor < pause:
        return 0.0
    cursor -= pause
    if cursor < travel:
        return cursor * speed
    cursor -= travel
    if cursor < pause:
        return overflow
    cursor -= pause
    return max(0.0, overflow - cursor * speed)
