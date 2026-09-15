"""Cinematique mort -> fantome : zoom, secousse, particules, emergence, recul."""

from __future__ import annotations

from enum import Enum, auto

import settings
from src.entities.ghost import Ghost
from src.entities.glow import draw_glow
from src.entities.particles import EmergenceBurst
from src.world.camera import CameraRig


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


class _Phase(Enum):
    ZOOM_IN = auto()
    BURST = auto()
    PAN_OUT = auto()
    DONE = auto()


class GhostEmergence:
    """Sequence finie autour du point de mort, avant que le joueur ne pilote."""

    def __init__(self, origin_x: float, origin_y: float) -> None:
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.particles = EmergenceBurst()
        self._phase = _Phase.ZOOM_IN
        self._elapsed = 0.0
        self._zoom_start = settings.CAMERA_ZOOM_PLAYER
        self._popped = False

    def capture_zoom(self, camera: CameraRig) -> None:
        self._zoom_start = camera.zoom

    @property
    def active(self) -> bool:
        return self._phase is not _Phase.DONE

    @property
    def shows_fog(self) -> bool:
        return self._phase is _Phase.PAN_OUT

    @property
    def fog_strength(self) -> float:
        if self._phase is not _Phase.PAN_OUT:
            return 0.0
        return _ease_in_out(self._elapsed / max(settings.DEATH_ZOOM_OUT_TIME, 0.001))

    @property
    def player_fade(self) -> float:
        """1 = corps encore dessine, 0 = uniquement le cadavre."""
        if self._phase is _Phase.ZOOM_IN:
            return 1.0
        if self._phase is _Phase.BURST:
            return 1.0 - _ease_out_cubic(self._elapsed / max(settings.DEATH_BURST_TIME, 0.001))
        return 0.0

    def update(self, delta_time: float, camera: CameraRig, ghost: Ghost) -> None:
        dt = max(0.0, delta_time)
        self._elapsed += dt
        self.particles.update(dt)
        if self._phase is _Phase.ZOOM_IN:
            self._tick_zoom_in(dt, camera, ghost)
        elif self._phase is _Phase.BURST:
            self._tick_burst(dt, camera, ghost)
        elif self._phase is _Phase.PAN_OUT:
            self._tick_pan_out(dt, camera, ghost)

    def draw_fx(self) -> None:
        """Flash d'ame + motes, au-dessus du corps et du fantome."""
        if self._phase is _Phase.BURST:
            t = min(1.0, self._elapsed / max(settings.DEATH_BURST_TIME, 0.001))
            size = settings.DEATH_FLASH_SIZE * (0.35 + 0.65 * t)
            alpha = int(settings.DEATH_FLASH_ALPHA * (1.0 - t) ** 2)
            if alpha > 0:
                draw_glow(
                    self.origin_x,
                    self.origin_y + settings.DEATH_EMERGE_LIFT * t * 0.5,
                    size,
                    size * 1.15,
                    settings.COLOR_GHOST_GLOW,
                    alpha,
                )
        self.particles.draw()

    def _tick_zoom_in(self, delta_time: float, camera: CameraRig, ghost: Ghost) -> None:
        duration = max(settings.DEATH_ZOOM_IN_TIME, 0.001)
        t = min(1.0, self._elapsed / duration)
        zoom = self._zoom_start + (
            settings.CAMERA_ZOOM_DEATH - self._zoom_start
        ) * _ease_out_cubic(t)
        camera.apply_cinematic(self.origin_x, self.origin_y, zoom, delta_time)
        ghost.tick_emerge(0.0)
        if t >= 1.0:
            self._phase = _Phase.BURST
            self._elapsed = 0.0
            camera.shake(settings.CAMERA_DEATH_SHAKE, settings.CAMERA_DEATH_SHAKE_TIME)
            self.particles.emit_burst(self.origin_x, self.origin_y)

    def _tick_burst(self, delta_time: float, camera: CameraRig, ghost: Ghost) -> None:
        duration = max(settings.DEATH_BURST_TIME, 0.001)
        t = min(1.0, self._elapsed / duration)
        camera.apply_cinematic(
            self.origin_x, self.origin_y, settings.CAMERA_ZOOM_DEATH, delta_time
        )
        self.particles.emit_stream(self.origin_x, self.origin_y, delta_time)
        emerge = _ease_out_cubic(t)
        ghost.tick_emerge(emerge)
        if not self._popped and t >= settings.DEATH_POP_AT:
            self._popped = True
            camera.shake(settings.CAMERA_DEATH_POP_SHAKE, settings.CAMERA_DEATH_POP_SHAKE_TIME)
            self.particles.emit_burst(ghost.center_x, ghost.center_y)
        if t >= 1.0:
            ghost.end_emerge()
            self._phase = _Phase.PAN_OUT
            self._elapsed = 0.0

    def _tick_pan_out(self, delta_time: float, camera: CameraRig, ghost: Ghost) -> None:
        duration = max(settings.DEATH_ZOOM_OUT_TIME, 0.001)
        t = min(1.0, self._elapsed / duration)
        zoom = settings.CAMERA_ZOOM_DEATH + (
            settings.CAMERA_ZOOM_GHOST - settings.CAMERA_ZOOM_DEATH
        ) * _ease_in_out(t)
        camera.apply_cinematic(ghost.center_x, ghost.center_y, zoom, delta_time)
        if t >= 1.0:
            self._phase = _Phase.DONE
