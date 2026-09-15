"""Progression du fantome : essence d'ame, paliers et statistiques.

Boucle : ennemi tue -> bille bleue -> essence -> palier du fantome -> bonus.
Les paliers se debloquent tout seuls (pas de shop).

Paliers d'ames cumulees (`settings.SOUL_LEVEL_THRESHOLDS`) :

    Niveau fantome | Ames cumulees | Bonus debloques
    -------------- | ------------- | ------------------------------------------
    1 (depart)     | 0             | stats de base (settings.GHOST_*)
    2              | 3             | Longe astrale I, Persistance I
    3              | 8             | Perception I
    4              | 15            | Poigne spectrale I
    5              | 25            | (aucun bonus extra pour l'instant)
    6              | 40            | (aucun bonus extra pour l'instant)

Bonus (additifs, se cumulent) :

    Nom                 | Effet
    ------------------- | --------------------------------
    Longe astrale I     | +120 px de portee autour du cadavre
    Persistance I       | +4 s de timer fantome
    Perception I        | +60 px de rayon de revelation
    Poigne spectrale I  | +1 objet transporte a la fois

Pour ajouter un palier : une entree dans `PALIERS` (et un seuil dans
`SOUL_LEVEL_THRESHOLDS` si le niveau n'existe pas encore).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import settings


@dataclass(frozen=True, slots=True)
class GhostStats:
    """Statistiques effectives du fantome pour une partie donnee."""

    max_range: float = settings.GHOST_MAX_RANGE
    duration: float = settings.GHOST_DURATION
    vision_radius: float = settings.GHOST_VISION_RADIUS
    carry_capacity: int = settings.GHOST_CARRY_CAPACITY

    def level_increased(self) -> "GhostStats":
        """Retourne une nouvelle instance avec les bonus d'un niveau supplementaire."""
        return replace(
            self,
            max_range=self.max_range + settings.GHOST_MAX_RANGE_INCREASE_VALUE,
            duration=self.duration + settings.GHOST_DURATION_INCREASE_VALUE,
            vision_radius=self.vision_radius + settings.GHOST_VISION_RADIUS_INCREASE_VALUE,
        )

    @staticmethod
    def for_level(level: int) -> "GhostStats":
        """Construit les stats de base pour un niveau donne (0 = aucun bonus)."""
        base = GhostStats()
        for _ in range(level):
            base = base.level_increased()
        return base


@dataclass(frozen=True, slots=True)
class Palier:
    """Bonus automatique a partir d'un niveau de fantome."""

    level: int
    name: str
    description: str
    range_bonus: float = 0.0
    duration_bonus: float = 0.0
    vision_bonus: float = 0.0
    carry_bonus: int = 0

    def __post_init__(self) -> None:
        if self.level < 1:
            raise ValueError("level doit etre >= 1")


# `level` = palier de `SOUL_LEVEL_THRESHOLDS` (1 = depart, 2 = 3 ames, ...).
PALIERS: tuple[Palier, ...] = (
    Palier(
        level=2,
        name="Longe astrale I",
        description="+120 px de portee autour du cadavre.",
        range_bonus=120.0,
    ),
    Palier(
        level=2,
        name="Persistance I",
        description="+4 s de duree en mode fantome.",
        duration_bonus=4.0,
    ),
    Palier(
        level=3,
        name="Perception I",
        description="+60 px de rayon de revelation.",
        vision_bonus=60.0,
    ),
    Palier(
        level=4,
        name="Poigne spectrale I",
        description="Transporte un objet supplementaire.",
        carry_bonus=1,
    ),
)


@dataclass(slots=True)
class SoulProgression:
    """Essence d'ame recoltee. Les paliers se debloquent tout seuls."""

    essence: int = 0
    collected_total: int = 0

    def absorb_orb(self, amount: int = settings.SOUL_ESSENCE_PER_ORB) -> None:
        """Convertit une bille bleue recoltee en essence d'ame."""
        if amount <= 0:
            raise ValueError("amount doit etre strictement positif")
        self.essence += amount
        self.collected_total += amount

    @property
    def level(self) -> int:
        """Niveau du fantome, deduit de l'essence totale recoltee."""
        level = 1
        for index, threshold in enumerate(settings.SOUL_LEVEL_THRESHOLDS):
            if self.collected_total >= threshold:
                level = index + 1
        return level

    @property
    def ghost_stats(self) -> GhostStats:
        """Statistiques du fantome correspondant au niveau actuel."""
        return GhostStats.for_level(self.level - 1)

    @property
    def essence_to_next_level(self) -> int | None:
        """Essence restante avant le prochain palier, ou None si palier max."""
        for threshold in settings.SOUL_LEVEL_THRESHOLDS:
            if self.collected_total < threshold:
                return threshold - self.collected_total
        return None

    def unlocked_paliers(self) -> tuple[Palier, ...]:
        """Paliers dont le niveau requis est atteint."""
        current = self.level
        return tuple(palier for palier in PALIERS if palier.level <= current)

    @property
    def ghost_stats(self) -> GhostStats:
        """Statistiques du fantome apres application des paliers atteints."""
        stats = GhostStats()
        for palier in self.unlocked_paliers():
            stats = GhostStats(
                max_range=stats.max_range + palier.range_bonus,
                duration=stats.duration + palier.duration_bonus,
                vision_radius=stats.vision_radius + palier.vision_bonus,
                carry_capacity=stats.carry_capacity + palier.carry_bonus,
            )
        return stats
