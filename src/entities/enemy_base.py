"""Classe de base commune aux ennemis (squelette, chauve-souris, ...).

Factorise ce qui est identique quel que soit l'archetype : les PV et la mort
(`take_damage`/`respawn`), le halo rouge en mode fantome (`draw_ghost_glow`) et
le test de portee d'une frappe (`strike_reaches`, via `attack_reach`/
`attack_vertical_range`). Le reste (l'IA a proprement parler, la physique, le
choix des animations) reste dans chaque sous-classe : ces comportements sont
trop differents (un squelette marche au sol, une chauve-souris vole librement)
pour qu'une factorisation plus poussee reste lisible.

Contrat pour une sous-classe :
    - appeler `super().__init__(...)` avec la texture initiale, les PV et la
      taille du corps (`body_width`/`body_height`, utilisee pour le
      pietinement, les plaques de pression et le halo) ;
    - appeler `_configure_glow(...)` une fois pour regler le halo ;
    - regler `attack_reach`/`attack_vertical_range` avant tout appel a
      `strike_reaches` (ou la surcharger si la forme de l'attaque ne s'y
      prete pas, voir `Bat.strike_reaches`) ;
    - implementer `_on_death()` (figer l'ennemi, lancer l'animation de mort)
      et `_on_respawn()` (reinitialiser etat/animation/orientation) ;
    - implementer `strike_active` (depend de l'animation et de l'etat en
      cours, propres a chaque sous-classe) ;
    - optionnel : surcharger `_on_hurt()` pour reagir a un coup non mortel
      (ennemi a plusieurs PV, voir `Zombie`).
"""

from __future__ import annotations

import math

import arcade

import settings
from src.entities.glow import draw_glow
from src.entities.item import Item, make_soul_orb


class EnemyBase(arcade.Sprite):
    """Ce que tous les ennemis ont en commun : PV, mort, halo, portee d'attaque."""

    # Un ennemi volant (chauve-souris) ne doit pas actionner les plaques de
    # pression : seuls les ennemis au sol pesent dessus. Surcharge par sous-classe.
    weighs_on_plates: bool = True

    def __init__(
        self,
        texture: arcade.Texture,
        *,
        center_x: float,
        center_y: float,
        hit_points: int,
        body_width: float,
        body_height: float,
    ) -> None:
        super().__init__(texture, center_x=center_x, center_y=center_y)
        self.hit_points = hit_points
        self.max_hit_points = hit_points
        self.body_width = body_width
        self.body_height = body_height
        self.attack_reach = 0.0
        self.attack_vertical_range = 0.0
        self.facing = -1
        self._is_dying = False
        self._knockback_x = 0.0
        self._hit_flash_left = 0.0
        self._base_color = self.color
        self._glow_time = (center_x * 0.13 + center_y * 0.07) % math.tau
        # Regle par `_configure_glow` ; des zeros par defaut donnent un halo invisible
        # plutot qu'une erreur si une sous-classe oublie de le configurer.
        self._glow_scale = 1.0
        self._glow_alpha = 0
        self._glow_inner_scale = 1.0
        self._glow_inner_alpha = 0
        self._glow_pulse = 0.0
        self._glow_pulse_speed = 1.0
        self._glow_color = (255, 0, 0)
        self._glow_color_core = (255, 0, 0)

    def _configure_glow(
        self,
        *,
        scale: float,
        alpha: int,
        inner_scale: float,
        inner_alpha: int,
        pulse: float,
        pulse_speed: float,
        color: tuple[int, int, int],
        color_core: tuple[int, int, int],
    ) -> None:
        """A appeler une fois dans `__init__` de la sous-classe."""
        self._glow_scale = scale
        self._glow_alpha = alpha
        self._glow_inner_scale = inner_scale
        self._glow_inner_alpha = inner_alpha
        self._glow_pulse = pulse
        self._glow_pulse_speed = pulse_speed
        self._glow_color = color
        self._glow_color_core = color_core

    # ------------------------------------------------------------------ #
    # Mort
    # ------------------------------------------------------------------ #

    @property
    def is_dying(self) -> bool:
        return self._is_dying

    def take_damage(self, amount: int = 1, knockback: float = 0.0) -> Item | None:
        """Applique des degats. Retourne la bille bleue si l'ennemi meurt.

        Un ennemi deja en train de mourir ignore tout nouveau coup : sans ca,
        un joueur qui reste sur sa tete pendant l'animation de mort ferait
        apparaitre plusieurs billes bleues pour un seul ennemi.
        `knockback` est un elan horizontal (frappe du joueur) : applique ici
        puis conserve par `_on_death` via `change_x` pour que le cadavre
        anime parte dans le sens du coup.
        """
        if amount <= 0:
            raise ValueError("amount doit etre strictement positif")
        if self._is_dying:
            return None
        self.hit_points -= amount
        self._apply_hit_feedback(knockback)
        if self.hit_points > 0:
            self._on_hurt()
            return None
        drop = self._death_drop()
        self._is_dying = True
        self._on_death()
        self.change_x = knockback
        return drop

    def _apply_hit_feedback(self, knockback: float) -> None:
        self._knockback_x = knockback
        self.change_x = knockback
        self._hit_flash_left = settings.ENEMY_HIT_FLASH_DURATION
        self.color = settings.COLOR_ENEMY_HIT

    def _tick_hit_feedback(self, delta_time: float) -> None:
        """Fait disparaitre le flash blanc du coup (a appeler dans `update`)."""
        self._hit_flash_left = max(0.0, self._hit_flash_left - delta_time)
        self.color = settings.COLOR_ENEMY_HIT if self._hit_flash_left > 0.0 else self._base_color

    def _on_hurt(self) -> None:
        """Coup encaisse sans mourir (ennemi a plusieurs PV, ex. `Zombie`).

        Ne fait rien par defaut : un ennemi a 1 PV n'y passe jamais.
        """

    def _death_drop(self) -> Item:
        """Objet laisse a la mort. Par defaut une bille bleue ; surchargeable
        (voir `Boss`, qui laisse une cle)."""
        return make_soul_orb(self.center_x, self.center_y)

    def _on_death(self) -> None:
        """Fige l'ennemi et lance son animation de mort. A implementer."""
        raise NotImplementedError

    def respawn(self, center_x: float, center_y: float) -> None:
        """Remet l'ennemi a un point de spawn, vivant et reinitialise.

        Repositionne, annule la vitesse acquise et restaure les PV. Ne touche
        pas a l'appartenance aux SpriteList : si l'ennemi avait ete retire via
        `take_damage`, c'est a l'appelant de le rajouter (voir
        `PlayView._update_respawn_enemies`).
        """
        self.center_x = center_x
        self.center_y = center_y
        self.change_x = 0.0
        self.change_y = 0.0
        self.hit_points = self.max_hit_points
        self._is_dying = False
        self._knockback_x = 0.0
        self._hit_flash_left = 0.0
        self.color = self._base_color
        self._on_respawn()

    def _on_respawn(self) -> None:
        """Reinitialise etat/animation/orientation. A implementer."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Attaque
    # ------------------------------------------------------------------ #

    @property
    def strike_active(self) -> bool:
        """Vrai pendant les frames ou l'attaque peut tuer. A implementer."""
        raise NotImplementedError

    def strike_reaches(self, target: arcade.Sprite) -> bool:
        """L'attaque, dirigee du cote ou regarde l'ennemi, atteint-elle `target` ?

        Compte aussi une cible collee contre (ou dans) le corps de l'ennemi.
        `attack_reach`/`attack_vertical_range` sont regles par la sous-classe ;
        une attaque qui ne vient pas seulement de face (ex. piquet vertical
        d'une chauve-souris) peut surcharger cette methode.
        """
        if not isinstance(target, arcade.Sprite):
            raise TypeError("target doit etre un arcade.Sprite")
        forward = (target.center_x - self.center_x) * self.facing
        if forward < -self.body_width / 2 or forward > self.attack_reach:
            return False
        return abs(target.center_y - self.center_y) <= self.attack_vertical_range

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #

    @property
    def glow_radius(self) -> float:
        """Rayon approximatif du halo, pour la marge de culling d'affichage
        (voir `PlayView._draw_enemy_glows`) : chaque archetype a sa propre
        echelle de halo (`_configure_glow`), donc pas de constante commune."""
        return max(self.body_width, self.body_height) * self._glow_scale

    def draw_ghost_glow(self, *, bind_blend: bool = True) -> None:
        """Halo rouge intense, dessine aussi hors du champ de vision."""
        pulse = 1.0 + self._glow_pulse * math.sin(self._glow_time * self._glow_pulse_speed)
        draw_glow(
            self.center_x,
            self.center_y,
            self.body_width * self._glow_scale,
            self.body_height * self._glow_scale,
            self._glow_color,
            int(self._glow_alpha * pulse),
            bind_blend=bind_blend,
        )
        draw_glow(
            self.center_x,
            self.center_y,
            self.body_width * self._glow_inner_scale,
            self.body_height * self._glow_inner_scale,
            self._glow_color_core,
            int(self._glow_inner_alpha * pulse),
            bind_blend=bind_blend,
        )
