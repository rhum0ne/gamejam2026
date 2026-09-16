"""Objets ramassables : cles, billes bleues (ames), et objets a venir.

Deux canaux de ramassage existent, volontairement distincts :
    - `body_can_pick`  : le corps physique marche dessus pour le recuperer ;
    - `ghost_can_carry`: le fantome le saisit a distance et le transporte
      jusqu'au cadavre pour le "livrer" au corps.

TODO(design) : la fiche concept est ambigue sur la bille bleue (recoltable
"uniquement par le corps physique" puis "le fantome recolte la bille bleue").
Le squelette autorise les deux ; a trancher en jam.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

import arcade

import settings
from src.entities.glow import draw_glow
from src.ui import sprites


class ItemKind(Enum):
    """Types d'objets ramassables."""

    KEY = auto()
    SOUL_ORB = auto()


@dataclass(frozen=True, slots=True)
class ItemProfile:
    """Caracteristiques immuables d'un type d'objet."""

    label: str
    color: tuple[int, int, int]
    size: int
    weight: int
    body_can_pick: bool
    ghost_can_carry: bool


ITEM_PROFILES: dict[ItemKind, ItemProfile] = {
    ItemKind.KEY: ItemProfile(
        label="Cle",
        color=settings.COLOR_KEY,
        size=settings.TILE_SIZE,
        weight=1,
        body_can_pick=True,
        ghost_can_carry=True,
    ),
    ItemKind.SOUL_ORB: ItemProfile(
        label="Ame",
        color=settings.COLOR_SOUL_ORB,
        size=settings.SOUL_ORB_SIZE,
        weight=1,
        body_can_pick=True,
        ghost_can_carry=True,
    ),
}

# Symboles utilises dans les cartes JSON.
ITEM_BY_MAP_SYMBOL: dict[str, ItemKind] = {
    "key": ItemKind.KEY,
    "soul_orb": ItemKind.SOUL_ORB,
}


def _texture_for(kind: ItemKind) -> arcade.Texture:
    if kind is ItemKind.KEY:
        return sprites.load_texture(settings.SPRITE_KEY)
    return sprites.soul_orb_texture()


class Item(arcade.Sprite):
    """Objet pose dans le niveau, eventuellement transporte par le fantome."""

    def __init__(self, kind: ItemKind, center_x: float, center_y: float) -> None:
        profile = ITEM_PROFILES[kind]
        super().__init__(_texture_for(kind), center_x=center_x, center_y=center_y)
        sprites.apply_rect_hit_box(self, profile.size, profile.size)
        self.kind = kind
        self.profile = profile
        self.carrier: arcade.Sprite | None = None
        self._rest_x = center_x
        self._rest_y = center_y
        self._elapsed = 0.0
        if kind is ItemKind.SOUL_ORB:
            self.color = profile.color
            self.alpha = settings.SOUL_ORB_ALPHA

    @property
    def is_carried(self) -> bool:
        return self.carrier is not None

    def attach_to(self, carrier: arcade.Sprite) -> None:
        """Fait suivre l'objet par `carrier` (typiquement le fantome)."""
        self.carrier = carrier

    def drop_at(self, center_x: float, center_y: float) -> None:
        """Depose l'objet a une position donnee."""
        self.carrier = None
        self._rest_x = center_x
        self._rest_y = center_y
        self.center_x = center_x
        self.center_y = center_y

    def draw_fx(self) -> None:
        """Aura de la bille bleue et halo dore des objets importants (cle)."""
        if self.kind is ItemKind.SOUL_ORB:
            pulse = 1.0 + settings.SOUL_ORB_GLOW_PULSE * math.sin(
                self._elapsed * settings.SOUL_ORB_GLOW_PULSE_SPEED
            )
            size = self.profile.size * settings.SOUL_ORB_GLOW_SCALE
            draw_glow(
                self.center_x,
                self.center_y,
                size,
                size,
                settings.COLOR_SOUL_ORB,
                int(settings.SOUL_ORB_GLOW_ALPHA * pulse),
            )
            return
        if self.kind is not ItemKind.KEY:
            return
        pulse = 1.0 + settings.KEY_GLOW_PULSE * math.sin(
            self._elapsed * settings.KEY_GLOW_PULSE_SPEED
        )
        size = self.profile.size * settings.KEY_GLOW_SCALE
        draw_glow(
            self.center_x,
            self.center_y,
            size,
            size,
            settings.COLOR_KEY_GLOW,
            int(settings.KEY_GLOW_ALPHA * pulse),
        )
        inner = self.profile.size * settings.KEY_GLOW_INNER_SCALE
        draw_glow(
            self.center_x,
            self.center_y,
            inner,
            inner,
            settings.COLOR_KEY_GLOW_CORE,
            int(settings.KEY_GLOW_INNER_ALPHA * pulse),
        )

    def update(
        self,
        delta_time: float = settings.FRAME_TIME,
        attractor: arcade.Sprite | None = None,
        *args,
        **kwargs,
    ) -> None:
        self._elapsed += delta_time
        if self.carrier is not None:
            self.center_x = self.carrier.center_x
            self.center_y = self.carrier.top + self.height / 2
            return
        if self.kind is ItemKind.SOUL_ORB:
            self._attract_toward(attractor, delta_time)
        offset = math.sin(self._elapsed * settings.ITEM_BOB_SPEED) * settings.ITEM_BOB_AMPLITUDE
        self.center_x = self._rest_x
        self.center_y = self._rest_y + offset

    def _attract_toward(self, attractor: arcade.Sprite | None, delta_time: float) -> None:
        if attractor is None:
            return
        offset_x = attractor.center_x - self._rest_x
        offset_y = attractor.center_y - self._rest_y
        distance = math.hypot(offset_x, offset_y)
        if distance > settings.SOUL_ORB_MAGNET_RANGE or distance == 0.0:
            return
        step = min(settings.SOUL_ORB_MAGNET_SPEED * max(delta_time, 0.0), distance)
        scale = step / distance
        self._rest_x += offset_x * scale
        self._rest_y += offset_y * scale


def make_soul_orb(center_x: float, center_y: float) -> Item:
    """Cree la bille bleue laissee par un ennemi vaincu."""
    return Item(ItemKind.SOUL_ORB, center_x, center_y)
