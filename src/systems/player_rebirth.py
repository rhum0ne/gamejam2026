"""Cinematique fantome -> corps : voile noir, reconstruction, reveal."""

from __future__ import annotations

from enum import Enum, auto

import settings
from src.entities.glow import draw_glow
from src.entities.particles import ReformBurst
from src.world.camera import CameraRig


def _ease_in_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * t


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


class _Phase(Enum):
    FADE_OUT = auto()
    FORM = auto()
    REVEAL = auto()
    DONE = auto()


class PlayerRebirth:
    """Sequence finie au checkpoint, avant que le joueur ne reprenne le controle."""

    def __init__(self, origin_x: float, origin_y: float) -> None:
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.particles = ReformBurst()
        self._phase = _Phase.FADE_OUT
        self._elapsed = 0.0
        self._needs_body = False
        self._popped = False

    @property
    def active(self) -> bool:
        return self._phase is not _Phase.DONE

    @property
    def shows_world(self) -> bool:
        return self._phase is not _Phase.FORM

    @property
    def shows_player(self) -> bool:
        return self._phase in (_Phase.FORM, _Phase.REVEAL)

    @property
    def covers_hud(self) -> bool:
        """Le voile passe par-dessus le HUD (extinction)."""
        return self._phase is _Phase.FADE_OUT

    @property
    def veil(self) -> float:
        if self._phase is _Phase.FADE_OUT:
            return _ease_in_cubic(self._elapsed / max(settings.REBIRTH_FADE_OUT_TIME, 0.001))
        if self._phase is _Phase.FORM:
            return 1.0
        if self._phase is _Phase.REVEAL:
            return 1.0 - _ease_out_cubic(
                self._elapsed / max(settings.REBIRTH_REVEAL_TIME, 0.001)
            )
        return 0.0

    @property
    def hud_alpha(self) -> float:
        if self._phase is _Phase.FADE_OUT:
            return 1.0
        if self._phase is _Phase.REVEAL:
            duration = max(settings.REBIRTH_REVEAL_TIME, 0.001)
            t = self._elapsed / duration
            start = settings.REBIRTH_HUD_AT
            if t <= start:
                return 0.0
            return _ease_out_cubic((t - start) / max(1.0 - start, 0.001))
        return 0.0

    @property
    def player_alpha(self) -> float:
        if self._phase is _Phase.REVEAL:
            return 1.0
        if self._phase is not _Phase.FORM:
            return 0.0
        duration = max(settings.REBIRTH_FORM_TIME, 0.001)
        t = self._elapsed / duration
        start = settings.REBIRTH_PLAYER_AT
        if t <= start:
            return 0.0
        return _ease_out_cubic((t - start) / max(1.0 - start, 0.001))

    def consume_body_spawn(self) -> bool:
        """True une fois, au passage en reconstruction."""
        if not self._needs_body:
            return False
        self._needs_body = False
        return True

    def update(self, delta_time: float, camera: CameraRig) -> None:
        dt = max(0.0, delta_time)
        self._elapsed += dt
        self.particles.update(dt)
        if self._phase is _Phase.FADE_OUT:
            self._tick_fade_out(dt, camera)
        elif self._phase is _Phase.FORM:
            self._tick_form(dt, camera)
        elif self._phase is _Phase.REVEAL:
            self._tick_reveal(dt, camera)

    def draw_fx(self) -> None:
        """Flash d'assemblage + motes, au-dessus du voile, avec le corps."""
        if self._phase is _Phase.FORM and self._popped:
            t = min(1.0, self._elapsed / max(settings.REBIRTH_FORM_TIME, 0.001))
            local = max(0.0, (t - settings.REBIRTH_PLAYER_AT) / max(1.0 - settings.REBIRTH_PLAYER_AT, 0.001))
            size = settings.REBIRTH_FLASH_SIZE * (0.45 + 0.55 * (1.0 - local))
            alpha = int(settings.REBIRTH_FLASH_ALPHA * (1.0 - local) ** 2)
            if alpha > 0:
                draw_glow(
                    self.origin_x,
                    self.origin_y,
                    size,
                    size * 1.2,
                    settings.COLOR_PLAYER,
                    alpha,
                )
        self.particles.draw()

    def _tick_fade_out(self, delta_time: float, camera: CameraRig) -> None:
        duration = max(settings.REBIRTH_FADE_OUT_TIME, 0.001)
        camera.drift_to(
            self.origin_x,
            self.origin_y,
            delta_time,
            zoom=settings.CAMERA_ZOOM_REBIRTH,
        )
        if self._elapsed / duration >= 1.0:
            self._phase = _Phase.FORM
            self._elapsed = 0.0
            self._needs_body = True

    def _tick_form(self, delta_time: float, camera: CameraRig) -> None:
        duration = max(settings.REBIRTH_FORM_TIME, 0.001)
        t = min(1.0, self._elapsed / duration)
        camera.apply_cinematic(
            self.origin_x,
            self.origin_y,
            settings.CAMERA_ZOOM_REBIRTH,
            delta_time,
        )
        self.particles.emit_stream(self.origin_x, self.origin_y, delta_time)
        if not self._popped and t >= settings.REBIRTH_PLAYER_AT:
            self._popped = True
            camera.shake(settings.CAMERA_REBIRTH_SHAKE, settings.CAMERA_REBIRTH_SHAKE_TIME)
            self.particles.emit_collapse(self.origin_x, self.origin_y)
        if t >= 1.0:
            self._phase = _Phase.REVEAL
            self._elapsed = 0.0

    def _tick_reveal(self, delta_time: float, camera: CameraRig) -> None:
        duration = max(settings.REBIRTH_REVEAL_TIME, 0.001)
        t = min(1.0, self._elapsed / duration)
        zoom = settings.CAMERA_ZOOM_REBIRTH + (
            settings.CAMERA_ZOOM_PLAYER - settings.CAMERA_ZOOM_REBIRTH
        ) * _ease_in_out(t)
        camera.apply_cinematic(self.origin_x, self.origin_y, zoom, delta_time)
        if t >= 1.0:
            self._phase = _Phase.DONE
