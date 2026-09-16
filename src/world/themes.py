"""Theme de terrain d'une carte : quelle planche ground l'auto-tiling lit.

Les planches `ground`, `sand` et `rock` ont la meme disposition 16x16 :
changer de theme, c'est seulement changer le fichier. Une carte sans champ
`theme` (ou avec une chaine vide) utilise `ground`.
"""

from __future__ import annotations

from pathlib import Path

import settings


def theme_ids() -> tuple[str, ...]:
    """Identifiants connus, dans l'ordre d'affichage / de cycle."""
    return tuple(settings.GROUND_THEMES)


def normalize_theme(theme: str | None) -> str:
    """Retourne un identifiant valide, ou leve ValueError."""
    if theme is None:
        return settings.GROUND_THEME_DEFAULT
    if not isinstance(theme, str):
        raise TypeError("theme doit etre une chaine")
    key = theme.strip().lower()
    if not key:
        return settings.GROUND_THEME_DEFAULT
    if key not in settings.GROUND_THEMES:
        known = ", ".join(theme_ids())
        raise ValueError(f"theme inconnu : '{theme}' (attendus : {known})")
    return key


def parse_theme(raw: object) -> str:
    """Lit le champ JSON `theme` (absent / vide = ground)."""
    if raw is None:
        return settings.GROUND_THEME_DEFAULT
    if not isinstance(raw, str):
        raise ValueError("theme doit etre une chaine")
    return normalize_theme(raw)


def sheet_for(theme: str | None) -> Path:
    """Planche ground correspondant au theme (defaut = terre)."""
    return settings.GROUND_THEMES[normalize_theme(theme)]


def next_theme(current: str | None) -> str:
    """Passe au theme suivant, en boucle."""
    ids = theme_ids()
    key = normalize_theme(current)
    return ids[(ids.index(key) + 1) % len(ids)]


def theme_label(theme: str | None) -> str:
    """Libelle court pour l'editeur (sable, roche, terre)."""
    key = normalize_theme(theme)
    return settings.GROUND_THEME_LABELS.get(key, key)
