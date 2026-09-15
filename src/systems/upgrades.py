"""Progression du fantome : essence d'ame, niveaux et arbre de competences.

Boucle de progression (fiche concept, systeme 2) :
    ennemi tue -> bille bleue -> essence d'ame -> niveau du fantome -> upgrade.

Les ameliorations sont purement declaratives : une `Upgrade` ne contient que
des bonus additifs, et `SoulProgression.ghost_stats` recalcule les statistiques
finales a partir des ameliorations debloquees. Pour ajouter une amelioration,
il suffit d'ajouter une entree dans `UPGRADES`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import settings


@dataclass(frozen=True, slots=True)
class GhostStats:
    """Statistiques effectives du fantome pour une partie donnee."""

    max_range: float = settings.GHOST_MAX_RANGE
    duration: float = settings.GHOST_DURATION
    vision_radius: float = settings.GHOST_VISION_RADIUS
    carry_capacity: int = settings.GHOST_CARRY_CAPACITY


@dataclass(frozen=True, slots=True)
class Upgrade:
    """Noeud de l'arbre de competences."""

    identifier: str
    name: str
    description: str
    cost: int
    required_level: int
    requires: tuple[str, ...] = ()
    range_bonus: float = 0.0
    duration_bonus: float = 0.0
    vision_bonus: float = 0.0
    carry_bonus: int = 0


UPGRADES: tuple[Upgrade, ...] = (
    Upgrade(
        identifier="range_1",
        name="Longe astrale I",
        description="+120 px de portee autour du cadavre.",
        cost=3,
        required_level=1,
        range_bonus=120.0,
    ),
    Upgrade(
        identifier="duration_1",
        name="Persistance I",
        description="+4 s de duree en mode fantome.",
        cost=3,
        required_level=1,
        duration_bonus=4.0,
    ),
    Upgrade(
        identifier="vision_1",
        name="Perception I",
        description="+60 px de rayon de revelation.",
        cost=4,
        required_level=2,
        vision_bonus=60.0,
    ),
    Upgrade(
        identifier="carry_1",
        name="Poigne spectrale I",
        description="Transporte un objet supplementaire.",
        cost=6,
        required_level=3,
        requires=("range_1",),
        carry_bonus=1,
    ),
)

UPGRADES_BY_ID: dict[str, Upgrade] = {upgrade.identifier: upgrade for upgrade in UPGRADES}


@dataclass(slots=True)
class SoulProgression:
    """Banque d'essence d'ame et ameliorations debloquees.

    L'instance vit dans la `GameSession` : elle survit aux changements de
    niveau et de vue (menu, arbre de competences, partie).
    """

    essence: int = 0
    collected_total: int = 0
    unlocked: set[str] = field(default_factory=set)

    # ------------------------------------------------------------------ #
    # Essence
    # ------------------------------------------------------------------ #

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
    def essence_to_next_level(self) -> int | None:
        """Essence restante avant le prochain niveau, ou None si niveau max."""
        for threshold in settings.SOUL_LEVEL_THRESHOLDS:
            if self.collected_total < threshold:
                return threshold - self.collected_total
        return None

    # ------------------------------------------------------------------ #
    # Arbre de competences
    # ------------------------------------------------------------------ #

    def is_unlocked(self, identifier: str) -> bool:
        return identifier in self.unlocked

    def can_unlock(self, identifier: str) -> bool:
        """Verifie cout, niveau requis et prerequis de l'amelioration."""
        upgrade = UPGRADES_BY_ID.get(identifier)
        if upgrade is None or identifier in self.unlocked:
            return False
        if self.essence < upgrade.cost or self.level < upgrade.required_level:
            return False
        return all(parent in self.unlocked for parent in upgrade.requires)

    def unlock(self, identifier: str) -> bool:
        """Debloque une amelioration si possible. Retourne True en cas de succes."""
        if not identifier:
            raise ValueError("identifier ne doit pas etre vide")
        if not self.can_unlock(identifier):
            return False
        self.essence -= UPGRADES_BY_ID[identifier].cost
        self.unlocked.add(identifier)
        return True

    @property
    def ghost_stats(self) -> GhostStats:
        """Statistiques du fantome apres application des ameliorations."""
        stats = GhostStats()
        for identifier in self.unlocked:
            upgrade = UPGRADES_BY_ID[identifier]
            stats = GhostStats(
                max_range=stats.max_range + upgrade.range_bonus,
                duration=stats.duration + upgrade.duration_bonus,
                vision_radius=stats.vision_radius + upgrade.vision_bonus,
                carry_capacity=stats.carry_capacity + upgrade.carry_bonus,
            )
        return stats
