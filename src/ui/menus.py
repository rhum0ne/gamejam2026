"""Ecrans hors-jeu : titre, game over, victoire, arbre de competences.

Les positions sont calculees d'apres la taille actuelle de la fenetre, pour
rester lisibles apres un redimensionnement ou un passage en plein ecran.
"""

from __future__ import annotations

import arcade

import settings
from src.systems.game_state import GameSession, PlayView
from src.systems.upgrades import UPGRADES, UPGRADES_BY_ID, Upgrade
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


def _draw_left(text: str, x: float, y: float, size: float, color: tuple[int, int, int]) -> None:
    _label(text, x, y, size, color, "left").draw()


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
        _draw_action(self, height * 0.42, ("t",), "Arbre de competences", self.held_keys)
        _draw_action(self, height * 0.36, ("f11",), "Plein ecran", self.held_keys)
        _draw_action(self, height * 0.30, ("esc",), "Quitter", self.held_keys)
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
        elif symbol == arcade.key.T:
            self.window.show_view(UpgradeTreeView(self.session, back_view=self))
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
        _draw_action(self, height * 0.40, ("t",), "Arbre de competences", self.held_keys)
        _draw_action(
            self, height * 0.34, ("esc",), "Menu principal", self.held_keys, color=settings.COLOR_MENU_HINT
        )

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        self.held_keys.add(symbol)
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.T:
            self.window.show_view(UpgradeTreeView(self.session, back_view=self))
        elif symbol == arcade.key.ESCAPE:
            self.window.show_view(TitleView(self.session))


class UpgradeTreeView(_HeldKeysMixin, arcade.View):
    """Arbre de competences : depense l'essence d'ame recoltee.

    Les ameliorations sont listees dans l'ordre de `UPGRADES` et se debloquent
    avec les touches 1 a 9.
    """

    def __init__(self, session: GameSession, back_view: arcade.View | None = None) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session
        self.back_view = back_view
        self.message = ""

    def on_show_view(self) -> None:
        use_default_camera(self.window)

    def on_draw(self) -> None:
        self.clear()
        width = self.window.width
        height = self.window.height
        progression = self.session.progression
        stats = progression.ghost_stats
        _draw_centered(self, "ARBRE DE COMPETENCES", height - 60, 32, settings.COLOR_MENU_TITLE)
        _draw_centered(
            self,
            f"Essence disponible : {progression.essence}  -  Niveau du fantome : {progression.level}",
            height - 100,
            18,
            settings.COLOR_HUD_TEXT,
        )
        _draw_centered(
            self,
            f"Portee {stats.max_range:.0f} px  -  Duree {stats.duration:.0f} s  -  "
            f"Vision {stats.vision_radius:.0f} px  -  Charge {stats.carry_capacity}",
            height - 130,
            15,
            settings.COLOR_MENU_HINT,
        )

        left = max(40.0, width * 0.06)
        top = height - 210
        for index, upgrade in enumerate(UPGRADES):
            y = top - index * 60
            unlocked = progression.is_unlocked(upgrade.identifier)
            available = progression.can_unlock(upgrade.identifier)
            if unlocked:
                color = settings.COLOR_DOOR_OPEN
                status = "DEBLOQUE"
            elif available:
                color = settings.COLOR_HUD_TEXT
                status = f"{upgrade.cost} essence"
            else:
                color = settings.COLOR_MENU_HINT
                status = f"{upgrade.cost} essence - {self._blocking_reason(upgrade)}"
            # 14, pas 18 : avec la police pixel, la ligne la plus longue
            # ("requiert <nom>") deborderait sinon de la fenetre.
            _draw_left(f"[{index + 1}] {upgrade.name}  ({status})", left, y, 14, color)
            _draw_left(upgrade.description, left + 30, y - 24, 14, settings.COLOR_MENU_HINT)

        if self.message:
            _draw_centered(self, self.message, 140, 16, settings.COLOR_SPIKE)
        _draw_action(
            self, 80, ("esc", "tab"), "Retour", self.held_keys, color=settings.COLOR_MENU_HINT
        )

    def _blocking_reason(self, upgrade: Upgrade) -> str:
        """Explique pourquoi une amelioration n'est pas encore accessible."""
        progression = self.session.progression
        missing = [
            UPGRADES_BY_ID[parent].name
            for parent in upgrade.requires
            if not progression.is_unlocked(parent)
        ]
        if missing:
            return f"requiert {', '.join(missing)}"
        if progression.level < upgrade.required_level:
            return f"niveau {upgrade.required_level} requis"
        return "essence insuffisante"

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        self.held_keys.add(symbol)
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.ESCAPE or symbol == arcade.key.TAB:
            self.window.show_view(self.back_view or TitleView(self.session))
            return
        index = symbol - arcade.key.KEY_1
        if 0 <= index < len(UPGRADES):
            upgrade = UPGRADES[index]
            if self.session.progression.unlock(upgrade.identifier):
                self.message = f"{upgrade.name} debloque !"
            else:
                self.message = "Amelioration indisponible (essence, niveau ou prerequis)."
