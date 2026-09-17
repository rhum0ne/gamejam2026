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
from src.ui.menu_kit import ButtonColumn, LevelCell, LevelGrid, TextButton, draw_panel
from src.ui.music import music
from src.ui.sfx import play_menu_hover
from src.ui.title_fx import TitleStage
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
    """Accueil : tableau de niveaux (lignes x colonnes)."""

    def __init__(self, session: GameSession | None = None) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session if session is not None else GameSession()
        self.stage = TitleStage()
        self.title_echo = arcade.Text(
            settings.GAME_TITLE,
            0,
            0,
            settings.COLOR_MENU_TITLE_SHADOW,
            font_size=settings.MENU_TITLE_SIZE,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        self.title = arcade.Text(
            settings.GAME_TITLE,
            0,
            0,
            settings.COLOR_MENU_TITLE,
            font_size=settings.MENU_TITLE_SIZE,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        self.level_name = arcade.Text(
            "",
            0,
            0,
            settings.COLOR_MENU_FOCUS,
            font_size=12,
            anchor_x="center",
            font_name=PIXEL_FONT,
        )
        self.grid = LevelGrid([], settings.MENU_GRID_COLUMNS)
        self.quit_button = TextButton("Quitter", on_activate=self._quit_game)
        self._on_quit = False
        self._panel = (0.0, 0.0, 0.0, 0.0)

    def on_show_view(self) -> None:
        use_default_camera(self.window)
        music.play_main_theme()
        self._rebuild()

    def on_resize(self, width: int, height: int) -> None:
        self._rebuild()

    def _rebuild(self) -> None:
        width, height = self.window.width, self.window.height
        cx = width / 2
        self.stage.resize(width, height)
        cells = []
        for index, filename in enumerate(settings.LEVEL_SEQUENCE):
            name, _subtitle = peek_level_info(filename)
            cells.append(
                LevelCell(
                    index,
                    name or f"Niveau {index + 1}",
                    on_activate=lambda chosen=index: self._open_level(chosen),
                )
            )
        self.grid = LevelGrid(cells, settings.MENU_GRID_COLUMNS)
        cols = settings.MENU_GRID_COLUMNS
        rows = max(1, (len(cells) + cols - 1) // cols)
        gap = settings.MENU_CELL_GAP
        cell_w = min(
            settings.MENU_CELL_WIDTH,
            max(96.0, (width * 0.72 - (cols - 1) * gap) / cols),
        )
        avail_h = height - 210
        cell_h = min(
            settings.MENU_CELL_HEIGHT,
            max(52.0, (avail_h - (rows - 1) * gap) / rows),
        )
        grid_w = cols * cell_w + (cols - 1) * gap
        grid_h = rows * cell_h + (rows - 1) * gap
        panel_w = grid_w + settings.MENU_PANEL_PAD * 2
        panel_h = grid_h + 118
        top = height * 0.88
        self.title.x = cx
        self.title.y = top
        self.title_echo.x = cx + 3
        self.title_echo.y = top - 3
        panel_top = top - 40
        panel_bottom = panel_top - panel_h
        self._panel = (cx - panel_w / 2, cx + panel_w / 2, panel_bottom, panel_top)
        grid_top = panel_top - 28
        grid_bottom = self.grid.layout(cx, grid_top, cell_w, cell_h)
        self.level_name.x = cx
        self.level_name.y = grid_bottom - 24
        self.quit_button.place(cx, panel_bottom + 36, min(settings.MENU_BUTTON_WIDTH, panel_w - 40), settings.MENU_BUTTON_HEIGHT)
        self._on_quit = False
        self._sync_chrome()

    def _sync_chrome(self) -> None:
        self.quit_button.set_focused(self._on_quit)
        if self._on_quit:
            self.level_name.text = ""
        else:
            self.level_name.text = self.grid.focused_name

    def _open_level(self, index: int) -> None:
        self.session.restart()
        self.session.start_level(index)
        self.window.show_view(LevelIntroView(self.session))

    def _quit_game(self) -> None:
        self.window.close()

    def on_update(self, delta_time: float) -> None:
        self.stage.update(delta_time)

    def on_draw(self) -> None:
        self.stage.draw()
        self.title_echo.draw()
        self.title.draw()
        left, right, bottom, top = self._panel
        draw_panel(left, right, bottom, top, accent=settings.COLOR_MENU_FOCUS)
        self.grid.draw()
        self.level_name.draw()
        self.quit_button.draw()
        keys.draw_prompt_row(
            self.window.width / 2,
            28,
            (
                (("z", "q", "s", "d"), "bouger"),
                (("space",), "sauter"),
                (("shift",), "dash"),
            ),
            self.held_keys,
            height=20,
        )

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        self.held_keys.add(symbol)
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.ESCAPE:
            self._quit_game()
            return
        left = symbol in (arcade.key.LEFT, arcade.key.Q, arcade.key.A)
        right = symbol in (arcade.key.RIGHT, arcade.key.D)
        up = symbol in (arcade.key.UP, arcade.key.W, arcade.key.Z)
        down = symbol in (arcade.key.DOWN, arcade.key.S)
        if self._on_quit:
            if up or left or right:
                self._on_quit = False
                self.grid.focus_last_row()
                self._sync_chrome()
                play_menu_hover()
            elif symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER, arcade.key.SPACE):
                self._quit_game()
            return
        if left:
            self.grid.move(-1, 0)
        elif right:
            self.grid.move(1, 0)
        elif up:
            self.grid.move(0, -1)
        elif down:
            if not self.grid.move(0, 1):
                self._on_quit = True
                play_menu_hover()
        elif symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER, arcade.key.SPACE):
            self.grid.activate_focused()
        self._sync_chrome()

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        was_quit = self._on_quit
        previous_focus = self.grid.focus_index
        if self.grid.on_hover(x, y):
            self._on_quit = False
        self.quit_button.on_hover(x, y)
        if self.quit_button.hovered:
            self._on_quit = True
        if self._on_quit != was_quit and self.grid.focus_index == previous_focus:
            play_menu_hover()
        self._sync_chrome()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        self.grid.on_press(x, y)
        self.quit_button.on_press(x, y)

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int) -> None:
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        self.grid.on_release(x, y)
        self.quit_button.on_release(x, y)


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
        open_play_view(self.window, self.session)


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
    """Fin d'un niveau : suivant, recommencer, ou retour au tableau."""

    def __init__(self, session: GameSession) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session
        heading = "VICTOIRE" if session.is_last_level else "NIVEAU TERMINE"
        self.title = arcade.Text(
            heading,
            0,
            0,
            settings.COLOR_MENU_GOLD,
            font_size=20,
            anchor_x="center",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        self.level_label = arcade.Text(
            "",
            0,
            0,
            settings.COLOR_MENU_HINT,
            font_size=12,
            anchor_x="center",
            font_name=PIXEL_FONT,
        )
        self.stats = arcade.Text(
            "",
            0,
            0,
            settings.COLOR_HUD_TEXT,
            font_size=11,
            anchor_x="center",
            font_name=PIXEL_FONT,
        )
        self.column = ButtonColumn()
        self._panel = (0.0, 0.0, 0.0, 0.0)

    def on_show_view(self) -> None:
        use_default_camera(self.window)
        name, _subtitle = peek_level_info(self.session.level_file)
        self.level_label.text = name
        progression = self.session.progression
        self.stats.text = (
            f"{progression.collected_total} ames   nv.{progression.level}   "
            f"{self.session.deaths} morts"
        )
        self._rebuild()

    def on_resize(self, width: int, height: int) -> None:
        self._rebuild()

    def _rebuild(self) -> None:
        width, height = self.window.width, self.window.height
        cx, cy = width / 2, height / 2
        panel_w, panel_h = 420.0, 340.0
        left, right = cx - panel_w / 2, cx + panel_w / 2
        bottom, top = cy - panel_h / 2, cy + panel_h / 2
        self._panel = (left, right, bottom, top)
        self.title.x = cx
        self.title.y = top - 44
        self.level_label.x = cx
        self.level_label.y = self.title.y - 32
        self.stats.x = cx
        self.stats.y = self.level_label.y - 28
        buttons: list[TextButton] = []
        if not self.session.is_last_level:
            buttons.append(TextButton("Suivant", on_activate=self._next_level))
        buttons.append(TextButton("Reessayer", on_activate=self._retry_level))
        buttons.append(TextButton("Niveaux", on_activate=self._go_select))
        self.column.set_buttons(buttons)
        self.column.layout(cx, self.stats.y - 48)

    def _next_level(self) -> None:
        if not self.session.advance_level():
            self._go_select()
            return
        self.window.show_view(LevelIntroView(self.session))

    def _retry_level(self) -> None:
        self.window.show_view(LevelIntroView(self.session))

    def _go_select(self) -> None:
        if self.session.on_leave is not None:
            self.session.on_leave()
            return
        self.window.show_view(TitleView(self.session))

    def on_draw(self) -> None:
        self.clear()
        left, right, bottom, top = self._panel
        draw_panel(left, right, bottom, top, accent=settings.COLOR_MENU_GOLD)
        self.title.draw()
        self.level_label.draw()
        self.stats.draw()
        self.column.draw()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        self.held_keys.add(symbol)
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.ESCAPE:
            self._go_select()
            return
        self.column.on_key_press(symbol)

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        self.column.on_mouse_motion(x, y)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.column.on_mouse_press(x, y)

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int) -> None:
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.column.on_mouse_release(x, y)


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
