"""Cameras du jeu.

`CameraRig` regroupe les deux cameras dont une scene a besoin :
    - `world` : suit une cible (joueur OU fantome) avec un lissage, et reste
      confinee dans les limites du niveau ;
    - `ui`    : camera fixe, en coordonnees ecran, pour le HUD.

Utilisation typique dans une vue :

    self.camera.follow(self.player, delta_time)   # dans on_update
    self.camera.use_world()                       # dans on_draw
    ...dessin du monde...
    self.camera.use_ui()
    ...dessin du HUD...
"""

from __future__ import annotations

import arcade
from arcade.camera import Camera2D

import settings


class CameraRig:
    """Paire de cameras monde / interface avec suivi lisse et clamp de niveau."""

    def __init__(self, world_width: float = 0.0, world_height: float = 0.0) -> None:
        self.world = Camera2D()
        self.ui = Camera2D()
        self.world_width = world_width
        self.world_height = world_height

    def set_bounds(self, world_width: float, world_height: float) -> None:
        """Definit les dimensions du niveau utilisees pour le clamp."""
        self.world_width = world_width
        self.world_height = world_height

    def snap_to(self, target: arcade.Sprite) -> None:
        """Place instantanement la camera sur la cible (changement de niveau)."""
        self.world.position = self._clamp(target.center_x, target.center_y)

    def follow(self, target: arcade.Sprite, delta_time: float) -> None:
        """Rapproche la camera de la cible, avec une avance dans le sens du mouvement."""
        look_ahead_x = 0.0
        look_ahead_y = 0.0
        if target.change_x:
            look_ahead_x = settings.CAMERA_LOOK_AHEAD * (1 if target.change_x > 0 else -1)
        if target.change_y:
            look_ahead_y = settings.CAMERA_LOOK_AHEAD * (1 if target.change_y > 0 else -1)
        desired_x, desired_y = self._clamp(
            target.center_x + look_ahead_x,
            target.center_y + look_ahead_y,
        )
        current_x, current_y = self.world.position
        factor = min(1.0, settings.CAMERA_LERP * delta_time * settings.FPS)
        self.world.position = (
            current_x + (desired_x - current_x) * factor,
            current_y + (desired_y - current_y) * factor,
        )

    def use_world(self) -> None:
        self.world.use()

    def use_ui(self) -> None:
        self.ui.use()

    def on_resize(self, width: int, height: int) -> None:
        """Reajuste les viewports apres un redimensionnement de la fenetre."""
        self.world.match_window()
        self.ui.match_window()
        self.world.position = self._clamp(*self.world.position)

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
