"""Progression du fantome : experience, ames et ameliorations choisies.

Boucle : ennemi tue -> bille bleue -> XP (fait monter de niveau) + ame
(monnaie depensable) -> a chaque niveau gagne, le joueur choisit une des 3
cartes d'amelioration pour le fantome (`UPGRADE_KINDS`), payee en ames.

Deux courbes exponentielles pilotent l'economie :
    - `_xp_for_level`   : XP cumulee pour atteindre un niveau donne ;
    - `_upgrade_cost`   : prix en ames du prochain rang d'une amelioration,
      qui augmente a chaque fois que cette meme amelioration est reprise.

Contrairement a l'ancien systeme de paliers automatiques, rien ne se
debloque tout seul : `ghost_stats` ne reflete que les rangs effectivement
achetes via `apply_upgrade`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import settings

UPGRADE_KINDS: tuple[str, ...] = ("vision", "speed", "duration")

_UPGRADE_LABELS: dict[str, tuple[str, str]] = {
    "vision": ("Vision spectrale", "px de rayon de revelation"),
    "speed": ("Vitesse spectrale", "de vitesse de deplacement"),
    "duration": ("Endurance spectrale", "s de duree en mode fantome"),
}

_UPGRADE_BONUS: dict[str, float] = {
    "vision": settings.GHOST_UPGRADE_VISION_BONUS,
    "speed": settings.GHOST_UPGRADE_SPEED_BONUS,
    "duration": settings.GHOST_UPGRADE_DURATION_BONUS,
}


@dataclass(frozen=True, slots=True)
class GhostStats:
    """Statistiques effectives du fantome pour une partie donnee."""

    max_range: float = settings.GHOST_MAX_RANGE
    duration: float = settings.GHOST_DURATION
    vision_radius: float = settings.GHOST_VISION_RADIUS
    carry_capacity: int = settings.GHOST_CARRY_CAPACITY
    speed: float = settings.GHOST_SPEED


@dataclass(frozen=True, slots=True)
class UpgradeCard:
    """Une des 3 ameliorations proposees a la montee de niveau."""

    kind: str
    name: str
    description: str
    cost: int
    rank: int  # rang deja possede AVANT cet achat


def _xp_for_level(level: int) -> int:
    """XP cumulee necessaire pour atteindre `level` (>= 1, croissance exponentielle)."""
    if level <= 1:
        return 0
    growth = settings.SOUL_XP_GROWTH
    base = settings.SOUL_XP_BASE
    return round(base * (growth ** (level - 1) - 1) / (growth - 1))


def _upgrade_cost(rank: int) -> int:
    """Prix en ames du rang `rank + 1` d'une amelioration (rang 0 = jamais prise)."""
    return round(settings.SOUL_UPGRADE_BASE_COST * settings.SOUL_UPGRADE_COST_GROWTH**rank)


@dataclass(slots=True)
class SoulProgression:
    """Ames recoltees (XP cumulee + monnaie) et rangs d'amelioration achetes."""

    essence: int = 0
    collected_total: int = 0
    upgrade_ranks: dict[str, int] = field(default_factory=lambda: dict.fromkeys(UPGRADE_KINDS, 0))

    def absorb_orb(self, amount: int = settings.SOUL_ESSENCE_PER_ORB) -> bool:
        """Convertit une bille bleue recoltee en XP + ames.

        Retourne True si cette recolte fait passer un niveau (a signaler par
        l'appelant pour ouvrir l'ecran de choix d'amelioration).
        """
        if amount <= 0:
            raise ValueError("amount doit etre strictement positif")
        level_before = self.level
        self.essence += amount
        self.collected_total += amount
        return self.level > level_before

    @property
    def level(self) -> int:
        """Niveau du fantome, deduit de l'XP totale recoltee."""
        level = 1
        while self.collected_total >= _xp_for_level(level + 1):
            level += 1
        return level

    @property
    def essence_to_next_level(self) -> int:
        """XP restante avant le prochain niveau (jamais de palier max : illimite)."""
        return max(0, _xp_for_level(self.level + 1) - self.collected_total)

    def upgrade_cost(self, kind: str) -> int:
        """Prix en ames du prochain rang de l'amelioration `kind`."""
        return _upgrade_cost(self.upgrade_ranks.get(kind, 0))

    def upgrade_cards(self) -> tuple[UpgradeCard, ...]:
        """Les 3 cartes proposees a chaque montee de niveau, prix courant inclus."""
        cards = []
        for kind in UPGRADE_KINDS:
            name, unit = _UPGRADE_LABELS[kind]
            rank = self.upgrade_ranks.get(kind, 0)
            amount = _UPGRADE_BONUS[kind]
            cards.append(
                UpgradeCard(
                    kind=kind,
                    name=name,
                    description=f"+{amount:g} {unit}",
                    cost=self.upgrade_cost(kind),
                    rank=rank,
                )
            )
        return tuple(cards)

    def apply_upgrade(self, kind: str) -> None:
        """Achete un rang de `kind` : ames depensees (plancher 0), rang incremente."""
        if kind not in UPGRADE_KINDS:
            raise ValueError(f"amelioration inconnue : '{kind}'")
        self.essence = max(0, self.essence - self.upgrade_cost(kind))
        self.upgrade_ranks[kind] = self.upgrade_ranks.get(kind, 0) + 1

    @property
    def ghost_stats(self) -> GhostStats:
        """Statistiques du fantome apres application des ameliorations achetees."""
        ranks = self.upgrade_ranks
        return GhostStats(
            vision_radius=(
                settings.GHOST_VISION_RADIUS
                + ranks.get("vision", 0) * settings.GHOST_UPGRADE_VISION_BONUS
            ),
            speed=(
                settings.GHOST_SPEED + ranks.get("speed", 0) * settings.GHOST_UPGRADE_SPEED_BONUS
            ),
            duration=(
                settings.GHOST_DURATION
                + ranks.get("duration", 0) * settings.GHOST_UPGRADE_DURATION_BONUS
            ),
        )
