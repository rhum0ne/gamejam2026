"""Cameras du jeu.

`CameraRig` regroupe les deux cameras dont une scene a besoin :
    - `world` : suit une cible (joueur OU fantome) avec un lissage exponentiel,
      independant du FPS, et reste confinee dans les limites du niveau ;
    - `ui`    : camera fixe, en coordonnees ecran, pour le HUD.

Une secousse optionnelle (`shake`) se superpose au suivi sans le deriver.

Le look-ahead n'est pas un cran binaire : il est proportionnel a la vitesse et
lui-meme lisse, pour eviter les a-coups quand `change_x` / `change_y` basculent
(physique au sol, sommet de saut, arret).
"""

from __future__ import annotations

import math

import arcade
from arcade.camera import Camera2D

import settings


def _exp_alpha(delta_time: float, smooth_time: float) -> float:
    """Facteur de lerp equivalent a une constante de temps, stable quel que soit le FPS."""
    if smooth_time <= 0.0:
        return 1.0
    return 1.0 - math.exp(-max(delta_time, 0.0) / smooth_time)


class CameraRig:
    """Paire de cameras monde / interface avec suivi lisse et clamp de niveau."""

    def __init__(self, world_width: float = 0.0, world_height: float = 0.0) -> None:
        self.world = Camera2D()
        self.ui = Camera2D()
        self.world_width = world_width
        self.world_height = world_height
        self._look_x = 0.0
        self._look_y = 0.0
        self._anchor_x = 0.0
        self._anchor_y = 0.0
        self._shake_x = 0.0
        self._shake_y = 0.0
        self._shake_time = 0.0
        self._shake_duration = 0.001
        self._shake_amp = 0.0
        self._shake_phase = 0.0

    def set_bounds(self, world_width: float, world_height: float) -> None:
        """Definit les dimensions du niveau utilisees pour le clamp."""
        self.world_width = world_width
        self.world_height = world_height

    def snap_to(self, target: arcade.Sprite) -> None:
        """Place instantanement la camera sur la cible (changement de niveau)."""
        self._look_x = 0.0
        self._look_y = 0.0
        self._shake_time = 0.0
        self._shake_x = 0.0
        self._shake_y = 0.0
        self._anchor_x, self._anchor_y = self._clamp(target.center_x, target.center_y)
        self._apply_offset()

    def shake(self, amplitude: float, duration: float) -> None:
        """Declenche une petite secousse (dash, impact)."""
        self._shake_amp = amplitude
        self._shake_duration = max(duration, 0.001)
        self._shake_time = self._shake_duration
        self._shake_phase = 0.0

    def follow(self, target: arcade.Sprite, delta_time: float) -> None:
        """Rapproche la camera de la cible, avec un look-ahead lisse."""
        self._ease_look_ahead(target, delta_time)
        desired_x, desired_y = self._clamp(
            target.center_x + self._look_x,
            target.center_y + self._look_y,
        )
        alpha = _exp_alpha(delta_time, settings.CAMERA_SMOOTH_TIME)
        self._anchor_x += (desired_x - self._anchor_x) * alpha
        self._anchor_y += (desired_y - self._anchor_y) * alpha
        self._tick_shake(delta_time)
        self._apply_offset()

    def use_world(self) -> None:
        self.world.use()

    def use_ui(self) -> None:
        self.ui.use()

    def on_resize(self, width: int, height: int) -> None:
        """Reajuste les viewports apres un redimensionnement de la fenetre."""
        self.world.match_window()
        self.ui.match_window(position=True)
        self._anchor_x, self._anchor_y = self._clamp(self._anchor_x, self._anchor_y)
        self._apply_offset()

    def _tick_shake(self, delta_time: float) -> None:
        if self._shake_time <= 0.0:
            self._shake_x = 0.0
            self._shake_y = 0.0
            return
        self._shake_time = max(0.0, self._shake_time - delta_time)
        strength = (self._shake_time / self._shake_duration) ** 2
        self._shake_phase += delta_time * 58.0
        self._shake_x = math.sin(self._shake_phase * 1.7) * self._shake_amp * strength
        self._shake_y = math.cos(self._shake_phase * 2.3) * self._shake_amp * 0.4 * strength

    def _apply_offset(self) -> None:
        self.world.position = (self._anchor_x + self._shake_x, self._anchor_y + self._shake_y)

    def _ease_look_ahead(self, target: arcade.Sprite, delta_time: float) -> None:
        max_speed = max(abs(settings.PLAYER_SPEED), abs(settings.GHOST_SPEED), 1.0)
        desired_x = max(-1.0, min(1.0, target.change_x / max_speed)) * settings.CAMERA_LOOK_AHEAD
        desired_y = 0.0
        if target.change_y < -settings.CAMERA_FALL_LOOK_THRESHOLD:
            desired_y = -settings.CAMERA_LOOK_AHEAD
        elif target.change_y > settings.CAMERA_RISE_LOOK_THRESHOLD:
            desired_y = settings.CAMERA_LOOK_AHEAD * 0.35
        alpha = _exp_alpha(delta_time, settings.CAMERA_LOOK_SMOOTH_TIME)
        self._look_x += (desired_x - self._look_x) * alpha
        self._look_y += (desired_y - self._look_y) * alpha

    def _clamp(self, x: float, y: float) -> tuple[float, float]:
        """Garde le cadre de la camera a l'interieur du niveau."""
        half_width = self.world.viewport_width / 2
        half_height = self.world.viewport_height / 2
        if self.world_width > 2 * half_width:
            x = min(max(x, half_width), self.world_width - half_width)
        else:
            x = self.world_width / 2
        if self.world_height > 2 * half_height:
            y = min(max(y, half_height), self.world_height - half_height)
        else:
            y = self.world_height / 2
        return x, y
