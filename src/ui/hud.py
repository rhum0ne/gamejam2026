"""HUD en jeu : stats en icones, jauge d'XP, invites clavier.

Le HUD est "sans etat" : la vue de jeu construit un `HudData` a chaque frame et
le passe a `Hud.draw()`. Les objets `arcade.Text` sont crees une seule fois
(leur creation est couteuse) puis mis a jour via leur attribut `.text`.

Coin haut-droit : jauge d'XP (`Lvl. X` + barre remplie), puis l'icone de cle
seulement si le joueur en a une. Le timer du fantome est un chronometre
colle au sprite, pas une jauge HUD.
"""

from __future__ import annotations

from dataclasses import dataclass

import arcade
from arcade.color import WHITE
from arcade.types import XYWH

import settings
from src.ui import keys, sprites
from src.ui.fonts import PIXEL_FONT


@dataclass(frozen=True, slots=True)
class HudData:
    """Instantane des informations a afficher."""

    level_name: str
    state_label: str
    essence: int
    ghost_level: int
    xp_ratio: float = 0.0
    hint: str = ""
    has_key: bool = False
    corpse_count: int = 0
    ghost_time_left: float | None = None
    ghost_duration: float = settings.GHOST_DURATION
    leash_ratio: float = 0.0
    fps: float | None = None
    controls: str = ""
    pressed_keys: frozenset[int] = frozenset()
    show_esprit: bool = False
    attack_cooldown_left: float | None = None
    attack_stage: int = 0
    attack_queued: bool = False


class Hud:
    """Affichage des informations de jeu par-dessus la scene."""

    _MARGIN = 16

    def __init__(self, screen_width: int, screen_height: int) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._key_icon = sprites.load_trimmed_texture(
            settings.SPRITE_KEY, width=settings.HUD_KEY_ICON
        )
        self._build_texts()

    def _build_texts(self) -> None:
        screen_width, screen_height = self.screen_width, self.screen_height
        self._level_text = self._make_text("", self._MARGIN, screen_height - 30)
        self._state_text = self._make_text("", self._MARGIN, screen_height - 54, size=13)
        self._attack_text = self._make_text("", self._MARGIN, screen_height - 78, size=13)
        self._ghost_level_text = arcade.Text(
            "Lvl. 1",
            0,
            0,
            settings.COLOR_HUD_TEXT,
            font_size=settings.HUD_GAUGE_LABEL_SIZE,
            anchor_x="right",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        self._hint_text = self._make_text(
            "", screen_width / 2, self._MARGIN + 6, size=13, anchor_x="center"
        )
        self._fps_text = self._make_text(
            "", self._MARGIN, self._MARGIN + 6, size=12, color=settings.COLOR_MENU_HINT
        )

    def _make_text(
        self,
        content: str,
        x: float,
        y: float,
        size: float = 16,
        anchor_x: str = "left",
        color: tuple[int, int, int] = settings.COLOR_HUD_TEXT,
    ) -> arcade.Text:
        return arcade.Text(
            content,
            x,
            y,
            color,
            font_size=size,
            anchor_x=anchor_x,
            font_name=PIXEL_FONT,
        )

    def draw(self, data: HudData, fade: float = 1.0) -> None:
        """Dessine le HUD a partir de l'instantane fourni."""
        fade = max(0.0, min(1.0, fade))
        if fade <= 0.02:
            return
        alpha = int(255 * fade)
        self._level_text.text = data.level_name
        self._state_text.text = data.state_label
        if data.attack_cooldown_left is not None:
            cooldown = max(0.0, data.attack_cooldown_left)
            if data.attack_stage > 0:
                queued = "  >" if data.attack_queued else ""
                self._attack_text.text = (
                    f"Combo : {data.attack_stage}/{settings.PLAYER_ATTACK_COMBO_COUNT}{queued}"
                )
            else:
                self._attack_text.text = (
                    "Attaque : prete" if cooldown <= 0.0 else f"Attaque : {cooldown:0.1f} s"
                )
        self._level_text.color = (*settings.COLOR_HUD_TEXT, alpha)
        self._state_text.color = (*settings.COLOR_HUD_TEXT, alpha)
        self._attack_text.color = (*settings.COLOR_HUD_TEXT, alpha)
        self._hint_text.text = data.hint
        self._hint_text.color = (*settings.COLOR_HUD_TEXT, alpha)

        self._level_text.draw()
        self._state_text.draw()
        if data.attack_cooldown_left is not None:
            self._attack_text.draw()
        self._draw_top_right(data, alpha)
        if data.fps is not None:
            self._fps_text.text = f"{data.fps:.0f} FPS"
            self._fps_text.color = (*settings.COLOR_MENU_HINT, alpha)
            self._fps_text.draw()
        if fade > 0.45:
            if data.controls == "playing":
                keys.draw_prompt_row(
                    self.screen_width / 2,
                    self._MARGIN + settings.UI_KEY_ICON_HEIGHT / 2 + 4,
                    keys.playing_prompts(show_esprit=data.show_esprit),
                    data.pressed_keys,
                )
            elif data.controls == "ghost":
                keys.draw_prompt_row(
                    self.screen_width / 2,
                    self._MARGIN + settings.UI_KEY_ICON_HEIGHT / 2 + 4,
                    keys.ghost_prompts(),
                    data.pressed_keys,
                )
            elif data.hint:
                self._hint_text.text = data.hint
                self._hint_text.draw()

    def _draw_top_right(self, data: HudData, alpha: int) -> None:
        """Jauge d'XP en haut, cle en dessous si le joueur en a une."""
        right = float(self.screen_width - self._MARGIN)
        gauge_row = max(settings.HUD_GAUGE_HEIGHT, settings.HUD_GAUGE_LABEL_SIZE) + 4
        y = self.screen_height - self._MARGIN
        self._draw_xp_gauge(
            right,
            y - gauge_row / 2,
            max(0.0, min(1.0, data.xp_ratio)),
            alpha,
            level=data.ghost_level,
        )
        if data.has_key:
            key_w = float(self._key_icon.width)
            key_h = float(self._key_icon.height)
            key_y = y - gauge_row - settings.HUD_STAT_GAP - key_h / 2
            self._draw_key_icon(right - key_w / 2, key_y, alpha)

    def _draw_key_icon(self, center_x: float, center_y: float, alpha: int) -> None:
        arcade.draw_texture_rect(
            self._key_icon,
            XYWH(
                center_x,
                center_y,
                self._key_icon.width,
                self._key_icon.height,
            ),
            pixelated=True,
            color=WHITE,
            alpha=alpha,
        )

    def _draw_xp_gauge(
        self,
        right: float,
        mid_y: float,
        ratio: float,
        alpha: int,
        *,
        level: int,
    ) -> None:
        """Jauge d'XP en haut a droite, libelle de niveau a gauche."""
        fill = (*settings.COLOR_HUD_BAR_FILL, alpha)
        back = (*settings.COLOR_HUD_BAR_BACKGROUND, alpha)
        width = settings.HUD_GAUGE_WIDTH
        height = settings.HUD_GAUGE_HEIGHT
        gap = settings.HUD_GAUGE_GAP
        bar_left = right - width
        bottom = mid_y - height / 2
        top = mid_y + height / 2
        self._ghost_level_text.text = f"Lvl. {level}"
        self._ghost_level_text.x = bar_left - gap
        self._ghost_level_text.y = mid_y
        self._ghost_level_text.color = (*settings.COLOR_HUD_TEXT, alpha)
        self._ghost_level_text.draw()
        arcade.draw_lrbt_rectangle_filled(bar_left, right, bottom, top, back)
        if ratio > 0.0:
            arcade.draw_lrbt_rectangle_filled(
                bar_left, bar_left + width * ratio, bottom, top, fill
            )
        arcade.draw_lrbt_rectangle_outline(bar_left, right, bottom, top, fill, 1)
