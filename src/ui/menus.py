"""Ecrans hors-jeu : titre, game over, victoire, arbre de competences.

Ces vues sont statiques, mais Arcade deconseille `draw_text` dans une boucle de
rendu. Les libelles passent donc par un petit cache d'objets `arcade.Text`
(`_label`) : le code reste aussi court qu'avec `draw_text`, sans le cout ni
l'avertissement de performance.

Chaque vue recoit la `GameSession` pour pouvoir afficher / modifier la
progression et relancer une partie.
"""

from __future__ import annotations

import arcade

import settings
from src.systems.game_state import GameSession, PlayView
from src.systems.upgrades import UPGRADES, UPGRADES_BY_ID, Upgrade

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
    key = (text, x, y, size, color, anchor_x)
    cached = _TEXT_CACHE.get(key)
    if cached is None:
        if len(_TEXT_CACHE) >= _TEXT_CACHE_LIMIT:
            _TEXT_CACHE.clear()
        cached = arcade.Text(text, x, y, color, font_size=size, anchor_x=anchor_x)
        _TEXT_CACHE[key] = cached
    return cached


def _draw_centered(text: str, y: float, size: float, color: tuple[int, int, int]) -> None:
    _label(text, settings.SCREEN_WIDTH / 2, y, size, color, "center").draw()


def _draw_left(text: str, x: float, y: float, size: float, color: tuple[int, int, int]) -> None:
    _label(text, x, y, size, color, "left").draw()


class TitleView(arcade.View):
    """Ecran titre : point d'entree de l'experience."""

    def __init__(self, session: GameSession | None = None) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session if session is not None else GameSession()

    def on_draw(self) -> None:
        self.clear()
        _draw_centered("PROJECT ASTRAL PLATFORMER", 500, 44, settings.COLOR_MENU_TITLE)
        _draw_centered("Dualite Joueur / Fantome", 450, 20, settings.COLOR_MENU_HINT)
        _draw_centered("ENTREE  -  Commencer l'aventure", 340, 20, settings.COLOR_HUD_TEXT)
        _draw_centered("T  -  Arbre de competences", 300, 20, settings.COLOR_HUD_TEXT)
        _draw_centered("ECHAP  -  Quitter", 260, 20, settings.COLOR_HUD_TEXT)
        _draw_centered(
            "Deplacements : ZQSD / fleches  -  Saut : Espace  -  Attaque : clic gauche  -  Esprit : F",
            160,
            15,
            settings.COLOR_MENU_HINT,
        )
        _draw_centered(
            "Mode fantome : traverse les murs spectraux, ramene les objets au cadavre.",
            130,
            15,
            settings.COLOR_MENU_HINT,
        )

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol in (arcade.key.ENTER, arcade.key.NUM_ENTER, arcade.key.SPACE):
            self.session.restart()
            self.window.show_view(PlayView(self.session))
        elif symbol == arcade.key.T:
            self.window.show_view(UpgradeTreeView(self.session, back_view=self))
        elif symbol == arcade.key.ESCAPE:
            self.window.close()


class GameOverView(arcade.View):
    """Ecran de fin de partie (reserve aux modes a vies limitees)."""

    def __init__(self, session: GameSession) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session

    def on_draw(self) -> None:
        self.clear()
        _draw_centered("GAME OVER", 460, 44, settings.COLOR_SPIKE)
        _draw_centered(f"Morts : {self.session.deaths}", 400, 20, settings.COLOR_HUD_TEXT)
        _draw_centered("ENTREE  -  Reessayer", 320, 20, settings.COLOR_HUD_TEXT)
        _draw_centered("ECHAP  -  Menu principal", 280, 20, settings.COLOR_MENU_HINT)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol in (arcade.key.ENTER, arcade.key.NUM_ENTER):
            self.window.show_view(PlayView(self.session))
        elif symbol == arcade.key.ESCAPE:
            self.window.show_view(TitleView(self.session))


class VictoryView(arcade.View):
    """Ecran affiche quand le dernier niveau de `LEVEL_SEQUENCE` est termine."""

    def __init__(self, session: GameSession) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session

    def on_draw(self) -> None:
        self.clear()
        progression = self.session.progression
        _draw_centered("VICTOIRE", 470, 44, settings.COLOR_DOOR_OPEN)
        _draw_centered(
            f"Ames recoltees : {progression.collected_total}  -  Fantome niveau {progression.level}",
            410,
            20,
            settings.COLOR_HUD_TEXT,
        )
        _draw_centered(f"Morts : {self.session.deaths}", 375, 20, settings.COLOR_HUD_TEXT)
        _draw_centered("T  -  Arbre de competences", 300, 20, settings.COLOR_HUD_TEXT)
        _draw_centered("ECHAP  -  Menu principal", 260, 20, settings.COLOR_MENU_HINT)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.T:
            self.window.show_view(UpgradeTreeView(self.session, back_view=self))
        elif symbol == arcade.key.ESCAPE:
            self.window.show_view(TitleView(self.session))


class UpgradeTreeView(arcade.View):
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

    def on_draw(self) -> None:
        self.clear()
        progression = self.session.progression
        stats = progression.ghost_stats
        _draw_centered("ARBRE DE COMPETENCES", 660, 32, settings.COLOR_MENU_TITLE)
        _draw_centered(
            f"Essence disponible : {progression.essence}  -  Niveau du fantome : {progression.level}",
            620,
            18,
            settings.COLOR_HUD_TEXT,
        )
        _draw_centered(
            f"Portee {stats.max_range:.0f} px  -  Duree {stats.duration:.0f} s  -  "
            f"Vision {stats.vision_radius:.0f} px  -  Charge {stats.carry_capacity}",
            590,
            15,
            settings.COLOR_MENU_HINT,
        )

        top = 510
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
            _draw_left(f"[{index + 1}] {upgrade.name}  ({status})", 220, y, 18, color)
            _draw_left(upgrade.description, 250, y - 24, 14, settings.COLOR_MENU_HINT)

        if self.message:
            _draw_centered(self.message, 140, 16, settings.COLOR_SPIKE)
        _draw_centered("ECHAP  -  Retour", 100, 18, settings.COLOR_MENU_HINT)

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
