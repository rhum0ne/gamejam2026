"""Ecrans hors-jeu : titre, game over, victoire, erreur de carte.

Les positions sont calculees d'apres la taille actuelle de la fenetre, pour
rester lisibles apres un redimensionnement ou un passage en plein ecran.
"""

from __future__ import annotations

import sys

import arcade

import settings
from src.systems.game_state import GameSession, PlayView
from src.ui import keys
from src.ui.display import handle_display_key, use_default_camera
from src.ui.fonts import PIXEL_FONT
from src.world.level import peek_level_info, LevelFormatError

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
            self.window.show_view(LevelIntroView(self.session))
            open_play_view(self.window, self.session)
        elif symbol == arcade.key.ESCAPE:
            self.window.close()


class LevelIntroView(_HeldKeysMixin, arcade.View):
    """Ecran noir affichant le nom (et le sous-titre) du niveau a venir.

    Insere entre deux niveaux (et avant le tout premier) : le nom vient de
    `session.level_file`, lu via `peek_level_info` pour ne pas construire tout
    le niveau juste pour afficher son titre. Un appui sur une touche saute le
    fondu et enchaine directement sur `PlayView`, qui charge le niveau pour de
    vrai.
    """

    def __init__(self, session: GameSession) -> None:
        super().__init__()
        self.background_color = (0, 0, 0)
        self.session = session
        self.title, self.subtitle = peek_level_info(session.level_file)
        self._elapsed = 0.0
        self._title_text = arcade.Text(
            self.title,
            0,
            0,
            settings.COLOR_MENU_TITLE,
            font_size=settings.LEVEL_INTRO_TITLE_SIZE,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        self._subtitle_text = (
            arcade.Text(
                self.subtitle,
                0,
                0,
                settings.COLOR_MENU_HINT,
                font_size=settings.LEVEL_INTRO_SUBTITLE_SIZE,
                anchor_x="center",
                anchor_y="center",
                font_name=PIXEL_FONT,
            )
            if self.subtitle
            else None
        )

    def on_show_view(self) -> None:
        use_default_camera(self.window)

    @property
    def _duration(self) -> float:
        return settings.LEVEL_INTRO_FADE_TIME * 2 + settings.LEVEL_INTRO_HOLD_TIME

    def _alpha(self) -> float:
        fade = max(settings.LEVEL_INTRO_FADE_TIME, 0.001)
        hold_end = fade + settings.LEVEL_INTRO_HOLD_TIME
        if self._elapsed < fade:
            return self._elapsed / fade
        if self._elapsed < hold_end:
            return 1.0
        return max(0.0, (self._duration - self._elapsed) / fade)

    def on_draw(self) -> None:
        self.clear()
        width, height = self.window.width, self.window.height
        alpha = int(255 * self._alpha())
        self._title_text.x = width / 2
        self._title_text.y = height * 0.54
        self._title_text.color = (*settings.COLOR_MENU_TITLE, alpha)
        self._title_text.draw()
        if self._subtitle_text is not None:
            self._subtitle_text.x = width / 2
            self._subtitle_text.y = height * 0.46
            self._subtitle_text.color = (*settings.COLOR_MENU_HINT, alpha)
            self._subtitle_text.draw()

    def on_update(self, delta_time: float) -> None:
        self._elapsed += delta_time
        if self._elapsed >= self._duration:
            self._advance()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        self.held_keys.add(symbol)
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol in (
            arcade.key.ENTER,
            arcade.key.RETURN,
            arcade.key.NUM_ENTER,
            arcade.key.SPACE,
            arcade.key.ESCAPE,
        ):
            self._advance()

    def _advance(self) -> None:
        self.window.show_view(PlayView(self.session))


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
            open_play_view(self.window, self.session)
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


def open_play_view(window: arcade.Window, session: GameSession) -> None:
    """Ouvre le niveau, ou un ecran d'erreur si la carte est illisible.

    Sous Windows, pyglet avale les exceptions des handlers clavier
    (`Exception ignored on calling ctypes callback`). On les capte ici
    pour afficher un message lisible au lieu de rester sur le menu.
    """
    try:
        window.show_view(PlayView(session))
    except LevelFormatError as error:
        show_level_error(window, session, error)


def show_level_error(
    window: arcade.Window, session: GameSession, error: BaseException
) -> None:
    """Affiche l'ecran d'erreur de carte et recopie le message sur stderr."""
    message = f"Carte invalide ({session.level_file}) : {error}"
    print(message, file=sys.stderr)
    window.show_view(LevelErrorView(session, error))


class LevelErrorView(_HeldKeysMixin, arcade.View):
    """Ecran affiche quand le JSON d'une carte refuse de se charger."""

    def __init__(self, session: GameSession, error: BaseException) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session
        self.message = str(error)
        self._body: arcade.Text | None = None

    def on_show_view(self) -> None:
        use_default_camera(self.window)
        self._rebuild_body()

    def on_resize(self, width: int, height: int) -> None:
        self._rebuild_body()

    def _rebuild_body(self) -> None:
        width = max(280, int(self.window.width * 0.78))
        self._body = arcade.Text(
            self.message,
            self.window.width / 2,
            self.window.height * 0.46,
            settings.COLOR_HUD_TEXT,
            font_size=16,
            anchor_x="center",
            anchor_y="center",
            align="center",
            font_name=PIXEL_FONT,
            width=width,
            multiline=True,
        )

    def on_draw(self) -> None:
        self.clear()
        height = self.window.height
        _draw_centered(self, "CARTE INVALIDE", height * 0.74, 36, settings.COLOR_SPIKE)
        _draw_centered(
            self,
            f"Fichier : {self.session.level_file}",
            height * 0.64,
            18,
            settings.COLOR_MENU_HINT,
        )
        if self._body is None:
            self._rebuild_body()
        if self._body is not None:
            self._body.draw()
        _draw_action(self, height * 0.24, ("enter",), "Reessayer", self.held_keys)
        caption = "Retour editeur" if self.session.on_leave is not None else "Menu principal"
        _draw_action(
            self, height * 0.18, ("esc",), caption, self.held_keys, color=settings.COLOR_MENU_HINT
        )

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        self.held_keys.add(symbol)
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER):
            open_play_view(self.window, self.session)
        elif symbol == arcade.key.ESCAPE:
            if self.session.on_leave is not None:
                self.session.on_leave()
                return
            self.window.show_view(TitleView(self.session))
