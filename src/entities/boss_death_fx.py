"""Explosion de mort du boss : etincelles, braises, eclats, ondes et flashs."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import settings
from src.entities.batch_draw import QuadBatch
from src.entities.glow import draw_glow, glow_pass
from src.entities.particles import _Grain, _draw_glow_motes


@dataclass(slots=True)
class _Shock:
    x: float
    y: float
    life: float
    max_life: float
    size: float
    color: tuple[int, int, int]


@dataclass(slots=True)
class _Flash:
    x: float
    y: float
    life: float
    max_life: float
    size: float
    color: tuple[int, int, int]


class BossDeathFx:
    """Salves successives autour du golem jusqu'a extinction des grains."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng if rng is not None else random.Random()
        self._sparks: list[_Grain] = []
        self._embers: list[_Grain] = []
        self._shards: list[_Grain] = []
        self._shocks: list[_Shock] = []
        self._flashes: list[_Flash] = []
        self._spark_quads = QuadBatch(capacity=max(8, settings.BOSS_DEATH_FX_MAX))
        self._ember_quads = QuadBatch(capacity=max(8, settings.BOSS_DEATH_FX_MAX))
        self._shard_quads = QuadBatch(capacity=max(8, settings.BOSS_DEATH_FX_MAX))
        self._elapsed = 0.0
        self._next_boom = 0.0
        self._booms_left = 0
        self._stream_timer = 0.0
        self._shakes: list[tuple[float, float]] = []
        self.active = False

    def clear(self) -> None:
        self._sparks.clear()
        self._embers.clear()
        self._shards.clear()
        self._shocks.clear()
        self._flashes.clear()
        self._elapsed = 0.0
        self._next_boom = 0.0
        self._booms_left = 0
        self._stream_timer = 0.0
        self._shakes.clear()
        self.active = False

    def start(self, x: float, y: float) -> None:
        self.clear()
        self.active = True
        self._booms_left = settings.BOSS_DEATH_FX_BOOM_COUNT
        self._next_boom = 0.0
        self._boom(x, y, mega=True)

    def consume_shakes(self) -> list[tuple[float, float]]:
        pending = self._shakes
        self._shakes = []
        return pending

    def update(self, x: float, y: float, delta_time: float = settings.FRAME_TIME) -> None:
        if not self.active:
            return
        dt = max(0.0, delta_time)
        self._elapsed += dt
        if self._booms_left > 0 and self._elapsed >= self._next_boom:
            jitter_x = self._rng.uniform(
                -settings.BOSS_DEATH_FX_BOOM_SPREAD, settings.BOSS_DEATH_FX_BOOM_SPREAD
            )
            jitter_y = self._rng.uniform(
                -settings.BOSS_DEATH_FX_BOOM_SPREAD * 0.45,
                settings.BOSS_DEATH_FX_BOOM_SPREAD * 0.7,
            )
            self._boom(x + jitter_x, y + jitter_y, mega=False)
        self._stream_timer -= dt
        if self._elapsed < settings.BOSS_DEATH_FX_STREAM_TIME and self._stream_timer <= 0.0:
            self._stream_timer = settings.BOSS_DEATH_FX_STREAM_INTERVAL
            self._emit_embers(x, y, settings.BOSS_DEATH_FX_STREAM_COUNT, burst=False)
        self._tick_grains(self._sparks, dt, drag=1.4)
        self._tick_grains(self._embers, dt, drag=0.9)
        self._tick_grains(self._shards, dt, drag=1.7)
        self._shocks = [shock for shock in self._shocks if self._tick_life(shock, dt)]
        self._flashes = [flash for flash in self._flashes if self._tick_life(flash, dt)]
        self._sparks = self._sparks[-settings.BOSS_DEATH_FX_MAX :]
        self._embers = self._embers[-settings.BOSS_DEATH_FX_MAX :]
        self._shards = self._shards[-settings.BOSS_DEATH_FX_MAX :]
        if (
            self._booms_left <= 0
            and self._elapsed >= settings.BOSS_DEATH_FX_STREAM_TIME
            and not self._sparks
            and not self._embers
            and not self._shards
            and not self._shocks
            and not self._flashes
        ):
            self.active = False

    def draw(self) -> None:
        if not self.active and not self._sparks and not self._embers and not self._shards:
            return
        with glow_pass():
            for flash in self._flashes:
                fade = max(0.0, flash.life / flash.max_life)
                size = flash.size * (0.55 + 0.45 * fade)
                draw_glow(
                    flash.x, flash.y, size, size * 0.72, flash.color, int(230 * fade)
                )
                draw_glow(
                    flash.x,
                    flash.y,
                    size * 0.38,
                    size * 0.32,
                    settings.COLOR_BOSS_DEATH_FLASH_CORE,
                    int(255 * fade),
                )
            for shock in self._shocks:
                progress = 1.0 - max(0.0, shock.life / shock.max_life)
                size = shock.size * (0.12 + 0.88 * progress)
                alpha = int(200 * ((1.0 - progress) ** 1.4))
                if alpha <= 0:
                    continue
                draw_glow(shock.x, shock.y, size, size * 0.62, shock.color, alpha)
        _draw_glow_motes(
            self._sparks,
            self._spark_quads,
            glow_alpha=settings.BOSS_DEATH_FX_SPARK_GLOW_ALPHA,
            core_size=settings.BOSS_DEATH_FX_SPARK_CORE,
            core_alpha=settings.BOSS_DEATH_FX_SPARK_CORE_ALPHA,
            core_color=settings.COLOR_BOSS_GLOW_CORE,
        )
        _draw_glow_motes(
            self._embers,
            self._ember_quads,
            glow_alpha=settings.BOSS_DEATH_FX_EMBER_GLOW_ALPHA,
            core_size=settings.BOSS_DEATH_FX_EMBER_CORE,
            core_alpha=settings.BOSS_DEATH_FX_EMBER_CORE_ALPHA,
            core_color=settings.COLOR_BOSS_DEATH_EMBER_CORE,
        )
        min_size = settings.PARTICLE_MIN_DRAW_SIZE
        self._shard_quads.begin()
        for grain in self._shards:
            fade = max(0.0, min(1.0, grain.life / grain.max_life))
            size = max(min_size, grain.size * (0.5 + 0.5 * fade))
            alpha = int(235 * fade)
            if alpha <= 0:
                continue
            self._shard_quads.add(grain.x, grain.y, size, grain.color, alpha)
        self._shard_quads.flush()

    def _boom(self, x: float, y: float, *, mega: bool) -> None:
        self._booms_left = max(0, self._booms_left - 1)
        self._next_boom = self._elapsed + settings.BOSS_DEATH_FX_BOOM_INTERVAL
        scale = settings.BOSS_DEATH_FX_MEGA_SCALE if mega else 1.0
        spark_n = int(settings.BOSS_DEATH_FX_SPARKS * scale)
        ember_n = int(settings.BOSS_DEATH_FX_EMBERS * scale)
        shard_n = int(settings.BOSS_DEATH_FX_SHARDS * scale)
        self._emit_sparks(x, y, spark_n)
        self._emit_embers(x, y, ember_n, burst=True)
        self._emit_shards(x, y, shard_n)
        self._shocks.append(
            _Shock(
                x=x,
                y=y,
                life=settings.BOSS_DEATH_FX_SHOCK_LIFE,
                max_life=settings.BOSS_DEATH_FX_SHOCK_LIFE,
                size=settings.BOSS_DEATH_FX_SHOCK_SIZE * scale,
                color=settings.COLOR_BOSS_GLOW if mega else settings.COLOR_BOSS_DEATH_EMBER,
            )
        )
        if mega:
            self._shocks.append(
                _Shock(
                    x=x,
                    y=y,
                    life=settings.BOSS_DEATH_FX_SHOCK_LIFE * 1.35,
                    max_life=settings.BOSS_DEATH_FX_SHOCK_LIFE * 1.35,
                    size=settings.BOSS_DEATH_FX_SHOCK_SIZE * 1.55,
                    color=settings.COLOR_BOSS_DEATH_FLASH,
                )
            )
        self._flashes.append(
            _Flash(
                x=x,
                y=y,
                life=settings.BOSS_DEATH_FX_FLASH_LIFE,
                max_life=settings.BOSS_DEATH_FX_FLASH_LIFE,
                size=settings.BOSS_DEATH_FX_FLASH_SIZE * scale,
                color=settings.COLOR_BOSS_DEATH_FLASH if mega else settings.COLOR_BOSS_GLOW_CORE,
            )
        )
        if mega:
            self._shakes.append(
                (settings.CAMERA_BOSS_DEATH_SHAKE, settings.CAMERA_BOSS_DEATH_SHAKE_TIME)
            )
        else:
            self._shakes.append(
                (
                    settings.CAMERA_BOSS_DEATH_BOOM_SHAKE,
                    settings.CAMERA_BOSS_DEATH_BOOM_SHAKE_TIME,
                )
            )

    def _emit_sparks(self, x: float, y: float, count: int) -> None:
        for _ in range(count):
            angle = self._rng.uniform(0.0, math.tau)
            speed = self._rng.uniform(0.45, 1.0) * settings.BOSS_DEATH_FX_SPARK_SPEED
            life = settings.BOSS_DEATH_FX_SPARK_LIFE * self._rng.uniform(0.55, 1.25)
            size = self._rng.uniform(
                settings.BOSS_DEATH_FX_SPARK_SIZE_MIN,
                settings.BOSS_DEATH_FX_SPARK_SIZE_MAX,
            )
            color = (
                settings.COLOR_BOSS_GLOW_CORE
                if self._rng.random() > 0.4
                else settings.COLOR_BOSS_GLOW
            )
            self._sparks.append(
                _Grain(
                    x=x + self._rng.uniform(-8.0, 8.0),
                    y=y + self._rng.uniform(-8.0, 8.0),
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    life=life,
                    max_life=max(life, 0.001),
                    size=size,
                    gravity=settings.BOSS_DEATH_FX_SPARK_GRAVITY,
                    color=color,
                )
            )

    def _emit_embers(self, x: float, y: float, count: int, *, burst: bool) -> None:
        for _ in range(count):
            if burst:
                angle = self._rng.uniform(0.0, math.tau)
                speed = self._rng.uniform(0.3, 1.0) * settings.BOSS_DEATH_FX_EMBER_SPEED
            else:
                angle = self._rng.uniform(math.pi * 0.15, math.pi * 0.85)
                speed = self._rng.uniform(0.2, 0.7) * settings.BOSS_DEATH_FX_EMBER_SPEED
            life = settings.BOSS_DEATH_FX_EMBER_LIFE * self._rng.uniform(0.65, 1.3)
            size = self._rng.uniform(
                settings.BOSS_DEATH_FX_EMBER_SIZE_MIN,
                settings.BOSS_DEATH_FX_EMBER_SIZE_MAX,
            )
            color = (
                settings.COLOR_BOSS_DEATH_EMBER_CORE
                if self._rng.random() > 0.5
                else settings.COLOR_BOSS_DEATH_EMBER
            )
            self._embers.append(
                _Grain(
                    x=x + self._rng.uniform(-12.0, 12.0),
                    y=y + self._rng.uniform(-10.0, 14.0),
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed + self._rng.uniform(30.0, 90.0),
                    life=life,
                    max_life=max(life, 0.001),
                    size=size,
                    gravity=settings.BOSS_DEATH_FX_EMBER_GRAVITY,
                    color=color,
                )
            )

    def _emit_shards(self, x: float, y: float, count: int) -> None:
        for _ in range(count):
            angle = self._rng.uniform(-0.2, math.pi + 0.2)
            speed = self._rng.uniform(0.4, 1.0) * settings.BOSS_DEATH_FX_SHARD_SPEED
            life = settings.BOSS_DEATH_FX_SHARD_LIFE * self._rng.uniform(0.7, 1.25)
            size = self._rng.uniform(
                settings.BOSS_DEATH_FX_SHARD_SIZE_MIN,
                settings.BOSS_DEATH_FX_SHARD_SIZE_MAX,
            )
            color = (
                settings.COLOR_BOSS_DEATH_SHARD
                if self._rng.random() > 0.4
                else settings.COLOR_BOSS_DEATH_SHARD_DARK
            )
            self._shards.append(
                _Grain(
                    x=x + self._rng.uniform(-14.0, 14.0),
                    y=y + self._rng.uniform(-8.0, 16.0),
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed + self._rng.uniform(40.0, 140.0),
                    life=life,
                    max_life=max(life, 0.001),
                    size=size,
                    gravity=settings.BOSS_DEATH_FX_SHARD_GRAVITY,
                    color=color,
                )
            )

    def _tick_grains(self, grains: list[_Grain], dt: float, *, drag: float) -> None:
        alive = 0
        friction = max(0.0, 1.0 - drag * dt)
        for grain in grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            grain.vy -= grain.gravity * dt
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            grain.vx *= friction
            grains[alive] = grain
            alive += 1
        del grains[alive:]

    @staticmethod
    def _tick_life(item: _Shock | _Flash, dt: float) -> bool:
        item.life -= dt
        return item.life > 0.0
