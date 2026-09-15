"""Ecrans hors-jeu : titre, game over, victoire.

Les positions sont calculees d'apres la taille actuelle de la fenetre, pour
rester lisibles apres un redimensionnement ou un passage en plein ecran.
"""

from __future__ import annotations

import arcade

import settings
from src.systems.game_state import GameSession, PlayView
from src.ui import keys
from src.ui.display import handle_display_key, use_default_camera
from src.ui.fonts import PIXEL_FONT

_TEXT_CACHE: dict[tuple, arcade.Text] = {}
_TEXT_CACHE_LIMIT = 256


def _label(
    text: str,
    x: float,
    y: float,
    size: float,
    color: tuple[int, int, int],
    anchor_x: str,
) -> arcade.Text:
    """Retourne un objet Text reutilisable pour ce libelle."""
    key = (text, round(x), round(y), size, color, anchor_x)
    cached = _TEXT_CACHE.get(key)
    if cached is None:
        if len(_TEXT_CACHE) >= _TEXT_CACHE_LIMIT:
            _TEXT_CACHE.clear()
        cached = arcade.Text(
            text, x, y, color, font_size=size, anchor_x=anchor_x, font_name=PIXEL_FONT
        )
        _TEXT_CACHE[key] = cached
    return cached


def _draw_centered(
    view: arcade.View, text: str, y: float, size: float, color: tuple[int, int, int]
) -> None:
    _label(text, view.window.width / 2, y, size, color, "center").draw()


class _HeldKeysMixin:
    """Suit les touches enfoncees pour l'etat presse des icones."""

    held_keys: set[int]

    def __init__(self, *args, **kwargs) -> None:
        self.held_keys = set()
        super().__init__(*args, **kwargs)

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        self.held_keys.discard(symbol)


def _draw_action(
    view: arcade.View,
    y: float,
    names: tuple[str, ...],
    caption: str,
    held: set[int],
    *,
    color: tuple[int, int, int] = settings.COLOR_HUD_TEXT,
) -> None:
    keys.draw_prompt(
        view.window.width / 2,
        y,
        names,
        caption,
        held,
        height=36,
        caption_size=22,
        caption_color=color,
    )


class TitleView(_HeldKeysMixin, arcade.View):
    """Ecran titre : point d'entree de l'experience."""

    def __init__(self, session: GameSession | None = None) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session if session is not None else GameSession()

    def on_show_view(self) -> None:
        use_default_camera(self.window)

    def on_draw(self) -> None:
        self.clear()
        height = self.window.height
        _draw_centered(self, "PROJECT ASTRAL PLATFORMER", height * 0.70, 28, settings.COLOR_MENU_TITLE)
        _draw_centered(self, "Dualite Joueur / Fantome", height * 0.63, 20, settings.COLOR_MENU_HINT)
        _draw_action(self, height * 0.48, ("enter",), "Commencer l'aventure", self.held_keys)
        _draw_action(self, height * 0.42, ("f11",), "Plein ecran", self.held_keys)
        _draw_action(self, height * 0.36, ("esc",), "Quitter", self.held_keys)
        keys.draw_prompt_row(
            self.window.width / 2,
            height * 0.18,
            (
                (("z", "q", "s", "d"), "bouger"),
                (("space",), "sauter"),
                (("shift",), "dash"),
            ),
            self.held_keys,
            height=32,
        )
        _draw_centered(
            self,
            "Un secret dort au fond du premier puits.",
            height * 0.11,
            15,
            settings.COLOR_MENU_HINT,
        )

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        self.held_keys.add(symbol)
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER, arcade.key.SPACE):
            self.session.restart()
            self.window.show_view(PlayView(self.session))
        elif symbol == arcade.key.ESCAPE:
            self.window.close()


class GameOverView(_HeldKeysMixin, arcade.View):
    """Ecran de fin de partie (reserve aux modes a vies limitees)."""

    def __init__(self, session: GameSession) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session

    def on_show_view(self) -> None:
        use_default_camera(self.window)

    def on_draw(self) -> None:
        self.clear()
        height = self.window.height
        _draw_centered(self, "GAME OVER", height * 0.64, 44, settings.COLOR_SPIKE)
        _draw_centered(self, f"Morts : {self.session.deaths}", height * 0.55, 20, settings.COLOR_HUD_TEXT)
        _draw_action(self, height * 0.42, ("enter",), "Reessayer", self.held_keys)
        _draw_action(
            self, height * 0.36, ("esc",), "Menu principal", self.held_keys, color=settings.COLOR_MENU_HINT
        )

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        self.held_keys.add(symbol)
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER):
            self.window.show_view(PlayView(self.session))
        elif symbol == arcade.key.ESCAPE:
            if self.session.on_leave is not None:
                self.session.on_leave()
                return
            self.window.show_view(TitleView(self.session))


class VictoryView(_HeldKeysMixin, arcade.View):
    """Ecran affiche quand le dernier niveau de `LEVEL_SEQUENCE` est termine."""

    def __init__(self, session: GameSession) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session

    def on_show_view(self) -> None:
        use_default_camera(self.window)

    def on_draw(self) -> None:
        self.clear()
        height = self.window.height
        progression = self.session.progression
        _draw_centered(self, "VICTOIRE", height * 0.66, 44, settings.COLOR_DOOR_OPEN)
        _draw_centered(
            self,
            f"Ames recoltees : {progression.collected_total}  -  Fantome niveau {progression.level}",
            height * 0.56,
            20,
            settings.COLOR_HUD_TEXT,
        )
        _draw_centered(self, f"Morts : {self.session.deaths}", height * 0.50, 20, settings.COLOR_HUD_TEXT)
        _draw_action(
            self, height * 0.40, ("esc",), "Menu principal", self.held_keys, color=settings.COLOR_MENU_HINT
        )

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        self.held_keys.add(symbol)
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.ESCAPE:
            if self.session.on_leave is not None:
                self.session.on_leave()
                return
            self.window.show_view(TitleView(self.session))
