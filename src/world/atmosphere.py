"""Brouillard et nuages de premier plan, avec parallaxe agressive.

Les couches se dessinent apres le monde (et le voile du fantome) pour
passer devant tout le gameplay. Un facteur de parallaxe > 1 fait defiler
la couche plus vite que la camera : l'oeil lit ca comme de la profondeur.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import arcade
from arcade.camera import Camera2D
from PIL import Image

import settings

_FOG_TEXTURE_SIZE = 128
_CLOUD_TEXTURE_SIZE = 32
_FOG_VARIANTS = 3
_CLOUD_VARIANTS = 4


@dataclass(slots=True)
class _Puff:
    sprite: arcade.Sprite
    home_x: float
    home_y: float
    wrap_w: float
    wrap_h: float
    parallax: float
    drift_x: float
    drift_y: float
    bob_amp: float
    bob_speed: float
    bob_phase: float
    base_alpha: int
    pulse_speed: float
    pulse_phase: float


class ForegroundAtmosphere:
    """Brume et petits nuages colles a l'objectif, independants du niveau."""

    def __init__(self, seed: int = settings.ATMOSPHERE_SEED) -> None:
        if not isinstance(seed, int):
            raise TypeError("seed doit etre un int")
        self._time = 0.0
        self._fog_textures = tuple(
            _build_fog_texture(seed * 17 + index) for index in range(_FOG_VARIANTS)
        )
        self._cloud_textures = tuple(
            _build_cloud_texture(seed * 31 + index) for index in range(_CLOUD_VARIANTS)
        )
        self._puffs: list[_Puff] = []
        self._fog_sprites = arcade.SpriteList(use_spatial_hash=False, capacity=48)
        self._cloud_sprites = arcade.SpriteList(use_spatial_hash=False, capacity=64)
        rng = random.Random(seed)
        for spec in settings.ATMOSPHERE_FOG_LAYERS:
            self._spawn_layer(rng, spec, self._fog_textures, settings.ATMOSPHERE_FOG_COLOR, "fog")
        for spec in settings.ATMOSPHERE_CLOUD_LAYERS:
            self._spawn_layer(
                rng, spec, self._cloud_textures, settings.ATMOSPHERE_CLOUD_COLOR, "cloud"
            )

    @property
    def puff_count(self) -> int:
        return len(self._puffs)

    def update(self, delta_time: float) -> None:
        """Fait deriver les puffs ; le placement camera se fait au draw."""
        dt = max(0.0, delta_time)
        self._time += dt
        for puff in self._puffs:
            puff.home_x = (puff.home_x + puff.drift_x * dt) % puff.wrap_w
            puff.home_y = (puff.home_y + puff.drift_y * dt) % puff.wrap_h

    def draw(self, camera: Camera2D) -> None:
        """Place chaque puff autour de la camera puis dessine brouillard, puis nuages."""
        cam_x, cam_y = camera.position
        t = self._time
        for puff in self._puffs:
            sprite = puff.sprite
            bob = math.sin(t * puff.bob_speed + puff.bob_phase) * puff.bob_amp
            sprite.center_x = _parallax_place(puff.home_x, cam_x, puff.parallax, puff.wrap_w)
            sprite.center_y = _parallax_place(puff.home_y, cam_y, puff.parallax, puff.wrap_h) + bob
            pulse = 0.82 + 0.18 * math.sin(t * puff.pulse_speed + puff.pulse_phase)
            sprite.alpha = max(0, min(255, int(puff.base_alpha * pulse)))
        self._fog_sprites.draw()
        self._cloud_sprites.draw(pixelated=True)

    def _spawn_layer(
        self,
        rng: random.Random,
        spec: tuple[int, float, float, float, int, int, float, float],
        textures: tuple[arcade.Texture, ...],
        color: tuple[int, int, int],
        kind: str,
    ) -> None:
        count, parallax, size_min, size_max, alpha_min, alpha_max, drift, y_bias = spec
        wrap_w = settings.WORLD_VIEW_WIDTH + size_max
        wrap_h = settings.WORLD_VIEW_HEIGHT + size_max
        sprite_list = self._fog_sprites if kind == "fog" else self._cloud_sprites
        for _ in range(count):
            texture = textures[rng.randrange(len(textures))]
            size = rng.uniform(size_min, size_max)
            if kind == "fog":
                scale_x = (size / texture.width) * rng.uniform(1.5, 2.6)
                scale_y = (size / texture.height) * rng.uniform(0.38, 0.72)
                angle = rng.uniform(-18.0, 18.0)
                bob_amp = rng.uniform(4.0, 12.0)
                bob_speed = rng.uniform(0.15, 0.40)
                drift_x = drift * rng.uniform(0.45, 1.15) * rng.choice((-1.0, 1.0))
                drift_y = drift * rng.uniform(-0.12, 0.12)
            else:
                jitter = rng.uniform(0.85, 1.25)
                scale_x = (size / texture.width) * jitter
                scale_y = (size / texture.height) * rng.uniform(0.75, 1.15)
                angle = rng.uniform(-8.0, 8.0)
                bob_amp = rng.uniform(2.0, 7.0)
                bob_speed = rng.uniform(0.35, 0.90)
                drift_x = drift * rng.uniform(0.55, 1.25) * rng.choice((-1.0, 1.0))
                drift_y = drift * rng.uniform(-0.18, 0.18)
            sprite = arcade.Sprite(texture, scale=(scale_x, scale_y), angle=angle)
            sprite.color = color
            sprite.alpha = alpha_min
            sprite_list.append(sprite)
            vertical = rng.random() ** (1.0 + 2.0 * y_bias)
            self._puffs.append(
                _Puff(
                    sprite=sprite,
                    home_x=rng.random() * wrap_w,
                    home_y=vertical * wrap_h,
                    wrap_w=wrap_w,
                    wrap_h=wrap_h,
                    parallax=parallax,
                    drift_x=drift_x,
                    drift_y=drift_y,
                    bob_amp=bob_amp,
                    bob_speed=bob_speed,
                    bob_phase=rng.uniform(0.0, math.tau),
                    base_alpha=rng.randint(alpha_min, alpha_max),
                    pulse_speed=rng.uniform(0.25, 0.70),
                    pulse_phase=rng.uniform(0.0, math.tau),
                )
            )


def _parallax_place(home: float, camera: float, parallax: float, wrap: float) -> float:
    """Position monde d'un puff : defile de `parallax` fois le mouvement camera."""
    offset = (home - camera * parallax) % wrap
    return camera - wrap * 0.5 + offset


def _build_fog_texture(seed: int) -> arcade.Texture:
    """Tache douce, un peu etiree, pour les voiles de brume."""
    rng = random.Random(seed)
    size = _FOG_TEXTURE_SIZE
    radius = size / 2
    sigma_x = radius * rng.uniform(0.32, 0.42)
    sigma_y = radius * rng.uniform(0.22, 0.32)
    pixels = bytearray(size * size * 4)
    inv_x = 1.0 / (2.0 * sigma_x * sigma_x)
    inv_y = 1.0 / (2.0 * sigma_y * sigma_y)
    for y in range(size):
        dy = y + 0.5 - radius
        row = y * size * 4
        for x in range(size):
            dx = x + 0.5 - radius
            alpha = int(255 * math.exp(-(dx * dx * inv_x + dy * dy * inv_y)))
            if alpha == 0:
                continue
            index = row + x * 4
            pixels[index] = 255
            pixels[index + 1] = 255
            pixels[index + 2] = 255
            pixels[index + 3] = alpha
    image = Image.frombytes("RGBA", (size, size), bytes(pixels))
    return arcade.Texture(image, hash=f"atmosphere-fog-{seed}-{size}")


def _build_cloud_texture(seed: int) -> arcade.Texture:
    """Petit nuage pixelise : quelques taches gaussiennes superposees."""
    rng = random.Random(seed)
    size = _CLOUD_TEXTURE_SIZE
    accum = [0.0] * (size * size)
    blob_count = rng.randint(3, 5)
    for _ in range(blob_count):
        cx = rng.uniform(0.32, 0.68) * size
        cy = rng.uniform(0.38, 0.64) * size
        sigma = size * rng.uniform(0.10, 0.20)
        weight = rng.uniform(0.55, 1.0)
        inv = 1.0 / (2.0 * sigma * sigma)
        for y in range(size):
            dy = y + 0.5 - cy
            row = y * size
            for x in range(size):
                dx = x + 0.5 - cx
                accum[row + x] += weight * math.exp(-(dx * dx + dy * dy) * inv)
    peak = max(accum) or 1.0
    pixels = bytearray(size * size * 4)
    for index, value in enumerate(accum):
        alpha = int(255 * min(1.0, value / peak))
        if alpha == 0:
            continue
        pixel = index * 4
        pixels[pixel] = 255
        pixels[pixel + 1] = 255
        pixels[pixel + 2] = 255
        pixels[pixel + 3] = alpha
    image = Image.frombytes("RGBA", (size, size), bytes(pixels))
    return arcade.Texture(image, hash=f"atmosphere-cloud-{seed}-{size}")
