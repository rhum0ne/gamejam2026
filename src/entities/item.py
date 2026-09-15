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
        size=settings.ITEM_SIZE,
        weight=1,
        body_can_pick=True,
        ghost_can_carry=True,
    ),
    ItemKind.SOUL_ORB: ItemProfile(
        label="Ame",
        color=settings.COLOR_SOUL_ORB,
        size=settings.ITEM_SIZE - 4,
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


class Item(arcade.SpriteSolidColor):
    """Objet pose dans le niveau, eventuellement transporte par le fantome."""

    def __init__(self, kind: ItemKind, center_x: float, center_y: float) -> None:
        profile = ITEM_PROFILES[kind]
        super().__init__(
            profile.size,
            profile.size,
            center_x=center_x,
            center_y=center_y,
            color=profile.color,
        )
        self.kind = kind
        self.profile = profile
        self.carrier: arcade.Sprite | None = None
        self._rest_y = center_y
        self._elapsed = 0.0

    @property
    def is_carried(self) -> bool:
        return self.carrier is not None

    def attach_to(self, carrier: arcade.Sprite) -> None:
        """Fait suivre l'objet par `carrier` (typiquement le fantome)."""
        self.carrier = carrier

    def drop_at(self, center_x: float, center_y: float) -> None:
        """Depose l'objet a une position donnee."""
        self.carrier = None
        self.center_x = center_x
        self.center_y = center_y
        self._rest_y = center_y

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        self._elapsed += delta_time
        if self.carrier is not None:
            self.center_x = self.carrier.center_x
            self.center_y = self.carrier.top + self.height
            return
        offset = math.sin(self._elapsed * settings.ITEM_BOB_SPEED) * settings.ITEM_BOB_AMPLITUDE
        self.center_y = self._rest_y + offset


def make_soul_orb(center_x: float, center_y: float) -> Item:
    """Cree la bille bleue laissee par un ennemi vaincu."""
    return Item(ItemKind.SOUL_ORB, center_x, center_y)
