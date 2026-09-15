"""Obstacles statiques du decor.

Regle de collision fondamentale du jeu :
    - le corps physique est bloque par tous les murs ;
    - le fantome est bloque par les murs normaux mais traverse les murs
      spectraux (`SpectralWall`, symbole `=` dans les cartes).

Les sprites sont pour l'instant des rectangles de couleur unie
(`arcade.SpriteSolidColor`). Quand les assets graphiques arriveront, il suffira
de remplacer l'appel a `super().__init__()` par un chargement de texture depuis
`settings.SPRITES_DIR`.
"""

from __future__ import annotations

import arcade

import settings


class Wall(arcade.SpriteSolidColor):
    """Bloc de terrain plein, infranchissable pour tout le monde."""

    ghost_passable = False

    def __init__(
        self,
        center_x: float,
        center_y: float,
        size: int = settings.TILE_SIZE,
        color: tuple[int, int, int] = settings.COLOR_WALL,
    ) -> None:
        super().__init__(size, size, center_x=center_x, center_y=center_y, color=color)


class SpectralWall(Wall):
    """Mur que seul le fantome peut traverser.

    Indetectable pour le corps physique : il est peint comme de la roche
    normale et ne prend sa couleur spectrale que dans le champ de vision du
    fantome (fiche concept : "devoile les elements invisibles en mode normal").
    """

    ghost_passable = True

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        super().__init__(center_x, center_y, size=size, color=settings.COLOR_WALL)
        self.revealed = False

    def set_revealed(self, revealed: bool) -> None:
        """Affiche ou masque la nature spectrale du mur."""
        if revealed == self.revealed:
            return
        self.revealed = revealed
        self.color = settings.COLOR_SPECTRAL_WALL if revealed else settings.COLOR_WALL


class Spike(arcade.SpriteSolidColor):
    """Piques : mortelles pour le corps physique, inoffensives pour le fantome.

    La hitbox ne couvre que la moitie basse de la tuile pour que le joueur
    puisse raser les piques sans mourir injustement.
    """

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        height = size // 2
        super().__init__(
            size,
            height,
            center_x=center_x,
            center_y=center_y - (size - height) / 2,
            color=settings.COLOR_SPIKE,
        )
        self.lethal_for_body = True
        self.lethal_for_ghost = False


class HiddenSpike(Spike):
    """Piege invisible, signale par une nuee de petits fantomes."""

    hidden = True
    ghost_warning = True

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        super().__init__(center_x, center_y, size=size)
        self.lethal_for_body = False
        self.contact_time = 0.0

    @property
    def activation_ratio(self) -> float:
        """Progression de l'activation du piege, entre 0.0 et 1.0."""
        if settings.HIDDEN_TRAP_ACTIVATION_DELAY <= 0:
            return 1.0
        return min(1.0, self.contact_time / settings.HIDDEN_TRAP_ACTIVATION_DELAY)

    def update_contact(self, touching: bool, delta_time: float) -> None:
        """Arme le piege apres un contact continu, ou annule le compte a rebours."""
        if not touching:
            self.contact_time = 0.0
            self.lethal_for_body = False
            return
        self.contact_time = min(
            settings.HIDDEN_TRAP_ACTIVATION_DELAY,
            self.contact_time + max(0.0, delta_time),
        )
        self.lethal_for_body = self.activation_ratio >= 1.0


class Door(arcade.SpriteSolidColor):
    """Porte de fin de niveau, verrouillee jusqu'a l'obtention de la cle."""

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        super().__init__(
            size,
            size * 2,
            center_x=center_x,
            center_y=center_y + size / 2,
            color=settings.COLOR_DOOR_LOCKED,
        )
        self.locked = True

    def unlock(self) -> None:
        """Deverrouille la porte (feedback visuel provisoire : changement de couleur)."""
        if not self.locked:
            return
        self.locked = False
        self.color = settings.COLOR_DOOR_OPEN


class Checkpoint(arcade.SpriteSolidColor):
    """Point de reapparition du corps physique apres la fin du mode fantome."""

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        super().__init__(
            size // 2,
            size,
            center_x=center_x,
            center_y=center_y,
            color=settings.COLOR_CHECKPOINT,
        )
        self.active = False

    def activate(self) -> None:
        self.active = True


def is_solid_for_ghost(wall: arcade.Sprite) -> bool:
    """Indique si `wall` bloque le fantome."""
    return not getattr(wall, "ghost_passable", False)
