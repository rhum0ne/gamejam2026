"""Poussiere de pied : burst a l'atterrissage, grains pendant la course."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import arcade

import settings
from src.entities.glow import additive_blend, draw_glow


@dataclass(slots=True)
class _Grain:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    gravity: float
    color: tuple[int, int, int]


class DustParticles:
    """Nuage de petits rectangles, sans collision ni SpriteList."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._grains: list[_Grain] = []
        self._rng = rng if rng is not None else random.Random()
        self._run_timer = 0.0

    def clear(self) -> None:
        self._grains.clear()
        self._run_timer = 0.0

    def emit_landing(
        self,
        x: float,
        y: float,
        fall_speed: float,
        *,
        body_half: float = 12.0,
    ) -> None:
        """Eclabousse de poussiere sous les pieds, proportionnelle a la chute."""
        if fall_speed < settings.PARTICLE_LAND_MIN_SPEED:
            return
        span = max(0.001, settings.PARTICLE_LAND_MAX_SPEED - settings.PARTICLE_LAND_MIN_SPEED)
        impact = max(0.0, min(1.0, (fall_speed - settings.PARTICLE_LAND_MIN_SPEED) / span))
        count = settings.PARTICLE_LAND_COUNT_MIN + int(
            round((settings.PARTICLE_LAND_COUNT_MAX - settings.PARTICLE_LAND_COUNT_MIN) * impact)
        )
        for _ in range(count):
            side = self._rng.choice((-1.0, 1.0))
            speed_scale = 0.45 + 0.55 * impact
            vx = side * self._rng.uniform(0.35, 1.0) * settings.PARTICLE_LAND_SPEED_X * speed_scale
            vy = self._rng.uniform(0.25, 1.0) * settings.PARTICLE_LAND_SPEED_Y * speed_scale
            size = self._rng.uniform(
                settings.PARTICLE_LAND_SIZE_MIN,
                settings.PARTICLE_LAND_SIZE_MIN
                + (settings.PARTICLE_LAND_SIZE_MAX - settings.PARTICLE_LAND_SIZE_MIN)
                * (0.4 + 0.6 * impact),
            )
            life = settings.PARTICLE_LAND_LIFE * self._rng.uniform(0.7, 1.15)
            self._spawn(
                x + side * self._rng.uniform(body_half, body_half + 10.0),
                y + settings.PARTICLE_FOOT_CLEARANCE + self._rng.uniform(0.0, 4.0),
                vx,
                vy,
                life,
                size,
                settings.PARTICLE_LAND_GRAVITY,
            )

    def tick_run(self, x: float, y: float, facing: int, delta_time: float) -> None:
        """Emet un grain derriere le coureur, a intervalle regulier."""
        if self._run_timer <= 0.0:
            self._emit_run(x, y, facing)
            jitter = self._rng.uniform(0.75, 1.25)
            self._run_timer = settings.PARTICLE_RUN_INTERVAL * jitter
        else:
            self._run_timer -= max(0.0, delta_time)

    def stop_run(self) -> None:
        self._run_timer = 0.0

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        dt = max(0.0, delta_time)
        alive: list[_Grain] = []
        for grain in self._grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            grain.vy -= grain.gravity * dt
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            grain.vx *= max(0.0, 1.0 - 2.8 * dt)
            alive.append(grain)
        self._grains = alive[-settings.PARTICLE_MAX :]

    def draw(self) -> None:
        min_size = settings.PARTICLE_MIN_DRAW_SIZE
        for grain in self._grains:
            fade = max(0.0, min(1.0, grain.life / grain.max_life))
            size = max(min_size, grain.size * (0.55 + 0.45 * fade))
            alpha = int(230 * fade)
            if alpha <= 0:
                continue
            half = size / 2
            arcade.draw_lrbt_rectangle_filled(
                grain.x - half,
                grain.x + half,
                grain.y - half,
                grain.y + half,
                (*grain.color, alpha),
            )

    def _emit_run(self, x: float, y: float, facing: int) -> None:
        direction = -1.0 if facing >= 0 else 1.0
        vx = direction * self._rng.uniform(0.4, 1.0) * settings.PARTICLE_RUN_SPEED_X
        vy = self._rng.uniform(0.15, 1.0) * settings.PARTICLE_RUN_SPEED_Y
        life = settings.PARTICLE_RUN_LIFE * self._rng.uniform(0.75, 1.1)
        size = settings.PARTICLE_RUN_SIZE * self._rng.uniform(0.7, 1.15)
        self._spawn(
            x + direction * self._rng.uniform(6.0, 14.0),
            y + settings.PARTICLE_FOOT_CLEARANCE + self._rng.uniform(0.0, 3.0),
            vx,
            vy,
            life,
            size,
            settings.PARTICLE_LAND_GRAVITY * 0.55,
        )

    def _spawn(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        life: float,
        size: float,
        gravity: float,
    ) -> None:
        color = settings.COLOR_DUST if self._rng.random() > 0.35 else settings.COLOR_DUST_DARK
        self._grains.append(
            _Grain(
                x=x,
                y=y,
                vx=vx,
                vy=vy,
                life=life,
                max_life=max(life, 0.001),
                size=size,
                gravity=gravity,
                color=color,
            )
        )


class SoulBurst:
    """Eclat de motes bleues, utilise au respawn sur un checkpoint."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._grains: list[_Grain] = []
        self._rng = rng if rng is not None else random.Random()

    def clear(self) -> None:
        self._grains.clear()

    def emit(self, x: float, y: float) -> None:
        """Propulse un nuage de motes autour de `(x, y)`."""
        spread = settings.CHECKPOINT_BURST_SPREAD
        for _ in range(settings.CHECKPOINT_BURST_COUNT):
            angle = self._rng.uniform(math.pi * 0.18, math.pi * 0.82)
            speed_x = self._rng.uniform(0.25, 1.0) * settings.CHECKPOINT_BURST_SPEED_X
            speed_y = self._rng.uniform(0.45, 1.0) * settings.CHECKPOINT_BURST_SPEED_Y
            vx = math.cos(angle) * speed_x
            vy = math.sin(angle) * speed_y
            life = settings.CHECKPOINT_BURST_LIFE * self._rng.uniform(0.65, 1.15)
            size = self._rng.uniform(
                settings.CHECKPOINT_BURST_SIZE_MIN,
                settings.CHECKPOINT_BURST_SIZE_MAX,
            )
            color = (
                settings.COLOR_CHECKPOINT_PARTICLE_CORE
                if self._rng.random() > 0.55
                else settings.COLOR_CHECKPOINT_PARTICLE
            )
            self._grains.append(
                _Grain(
                    x=x + self._rng.uniform(-spread, spread),
                    y=y + self._rng.uniform(-spread * 0.4, spread),
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=max(life, 0.001),
                    size=size,
                    gravity=settings.CHECKPOINT_BURST_GRAVITY,
                    color=color,
                )
            )
        self._grains = self._grains[-settings.CHECKPOINT_BURST_MAX :]

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        dt = max(0.0, delta_time)
        alive: list[_Grain] = []
        for grain in self._grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            grain.vy -= grain.gravity * dt
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            grain.vx *= max(0.0, 1.0 - 1.6 * dt)
            alive.append(grain)
        self._grains = alive

    def draw(self) -> None:
        if not self._grains:
            return
        core = settings.CHECKPOINT_BURST_CORE_SIZE
        with additive_blend():
            for grain in self._grains:
                fade = max(0.0, min(1.0, grain.life / grain.max_life))
                alpha = int(settings.CHECKPOINT_BURST_GLOW_ALPHA * fade)
                if alpha <= 0:
                    continue
                draw_glow(
                    grain.x,
                    grain.y,
                    grain.size,
                    grain.size,
                    grain.color,
                    alpha,
                    bind_blend=False,
                )
        for grain in self._grains:
            fade = max(0.0, min(1.0, grain.life / grain.max_life))
            alpha = int(settings.CHECKPOINT_BURST_CORE_ALPHA * fade)
            if alpha <= 0:
                continue
            half = core * (0.45 + 0.55 * fade) / 2
            arcade.draw_lrbt_rectangle_filled(
                grain.x - half,
                grain.x + half,
                grain.y - half,
                grain.y + half,
                (*settings.COLOR_CHECKPOINT_PARTICLE_CORE, alpha),
            )
