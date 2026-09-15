"""Ecrans hors-jeu : titre, game over, victoire, arbre de competences.

Les positions sont calculees d'apres la taille actuelle de la fenetre, pour
rester lisibles apres un redimensionnement ou un passage en plein ecran.
"""

from __future__ import annotations

import arcade

import settings
from src.systems.game_state import GameSession, PlayView
from src.systems.upgrades import UPGRADES, UPGRADES_BY_ID, Upgrade
from src.ui.display import handle_display_key, use_default_camera

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
        cached = arcade.Text(text, x, y, color, font_size=size, anchor_x=anchor_x)
        _TEXT_CACHE[key] = cached
    return cached


def _draw_centered(
    view: arcade.View, text: str, y: float, size: float, color: tuple[int, int, int]
) -> None:
    _label(text, view.window.width / 2, y, size, color, "center").draw()


def _draw_left(text: str, x: float, y: float, size: float, color: tuple[int, int, int]) -> None:
    _label(text, x, y, size, color, "left").draw()


class TitleView(arcade.View):
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
        _draw_centered(self, "PROJECT ASTRAL PLATFORMER", height * 0.70, 44, settings.COLOR_MENU_TITLE)
        _draw_centered(self, "Dualite Joueur / Fantome", height * 0.63, 20, settings.COLOR_MENU_HINT)
        _draw_centered(self, "ENTREE  -  Commencer l'aventure", height * 0.48, 20, settings.COLOR_HUD_TEXT)
        _draw_centered(self, "T  -  Arbre de competences", height * 0.42, 20, settings.COLOR_HUD_TEXT)
        _draw_centered(self, "F11  -  Plein ecran", height * 0.36, 20, settings.COLOR_HUD_TEXT)
        _draw_centered(self, "ECHAP  -  Quitter", height * 0.30, 20, settings.COLOR_HUD_TEXT)
        _draw_centered(
            self,
            "Deplacements : ZQSD / fleches  -  Saut : Espace  -  Projeter l'esprit : F",
            height * 0.18,
            15,
            settings.COLOR_MENU_HINT,
        )
        _draw_centered(
            self,
            "Mode fantome : traverse les murs spectraux, ramene les objets au cadavre.",
            height * 0.13,
            15,
            settings.COLOR_MENU_HINT,
        )

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if handle_display_key(self.window, symbol, modifiers):
            return
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

    def on_show_view(self) -> None:
        use_default_camera(self.window)

    def on_draw(self) -> None:
        self.clear()
        height = self.window.height
        _draw_centered(self, "GAME OVER", height * 0.64, 44, settings.COLOR_SPIKE)
        _draw_centered(self, f"Morts : {self.session.deaths}", height * 0.55, 20, settings.COLOR_HUD_TEXT)
        _draw_centered(self, "ENTREE  -  Reessayer", height * 0.42, 20, settings.COLOR_HUD_TEXT)
        _draw_centered(self, "ECHAP  -  Menu principal", height * 0.36, 20, settings.COLOR_MENU_HINT)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if handle_display_key(self.window, symbol, modifiers):
            return
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
        _draw_centered(self, "T  -  Arbre de competences", height * 0.40, 20, settings.COLOR_HUD_TEXT)
        _draw_centered(self, "ECHAP  -  Menu principal", height * 0.34, 20, settings.COLOR_MENU_HINT)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if handle_display_key(self.window, symbol, modifiers):
            return
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

        left = max(48.0, width * 0.14)
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
            _draw_left(f"[{index + 1}] {upgrade.name}  ({status})", left, y, 18, color)
            _draw_left(upgrade.description, left + 30, y - 24, 14, settings.COLOR_MENU_HINT)

        if self.message:
            _draw_centered(self, self.message, 140, 16, settings.COLOR_SPIKE)
        _draw_centered(self, "ECHAP  -  Retour", 80, 18, settings.COLOR_MENU_HINT)

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
