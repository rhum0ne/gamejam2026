"""Detection des collisions "de gameplay".

Les collisions *physiques* (joueur contre murs, gravite) sont deja gerees par
`arcade.PhysicsEnginePlatformer` dans les entites. Ce module ne s'occupe que
des chocs qui declenchent une regle de jeu : mort sur les piques, ramassage
d'un objet, coup d'epee d'un ennemi, etc.

Convention : ces fonctions **ne modifient rien**, elles se contentent de
detecter et de retourner ce qui a ete touche. C'est l'appelant
(`src.systems.game_state`) qui applique les consequences. Cela rend les regles
testables sans fenetre Arcade.
"""

from __future__ import annotations

from collections.abc import Sequence
from collections.abc import Iterable

import arcade

import settings
from src.entities.corpse import Corpse
from src.entities.enemy import Enemy, EnemyState
from src.entities.ghost import Ghost
from src.entities.item import Item
from src.entities.player import Player
from src.world.level import Level
from src.world.obstacles import Checkpoint, Door


def player_hits_hazard(player: Player, level: Level) -> bool:
    """Le corps physique touche-t-il un piege mortel (piques) ?"""
    if not player.alive:
        return False
    for hazard_list in (level.hazards, level.falling_spikes):
        if any(
            getattr(hazard, "lethal_for_body", True)
            for hazard in arcade.check_for_collision_with_list(player, hazard_list)
        ):
            return True
    return False


def player_out_of_bounds(player: Player, level: Level) -> bool:
    """Le corps est-il sorti du niveau (chute dans le vide) ?"""
    return player.top < -settings.TILE_SIZE or player.center_x < -settings.TILE_SIZE


def items_reachable_by_body(player: Player, level: Level) -> list[Item]:
    """Objets que le corps physique peut ramasser en marchant dessus."""
    if not player.alive:
        return []
    return [
        item
        for item in arcade.check_for_collision_with_list(player, level.items)
        if item.profile.body_can_pick and not item.is_carried
    ]


def items_reachable_by_ghost(ghost: Ghost, level: Level) -> list[Item]:
    """Objets que le fantome peut saisir a distance."""
    return [
        item
        for item in arcade.check_for_collision_with_list(ghost, level.items)
        if item.profile.ghost_can_carry and not item.is_carried
    ]


def checkpoint_touched_by_player(player: Player, level: Level) -> Checkpoint | None:
    """Checkpoint en contact avec le corps physique, s'il y en a un."""
    if not player.alive:
        return None
    touched = arcade.check_for_collision_with_list(player, level.checkpoints)
    return touched[0] if touched else None


def door_touched_by_player(player: Player, level: Level) -> Door | None:
    """Porte en contact avec le corps physique, s'il y en a une."""
    doors = arcade.check_for_collision_with_list(player, level.doors)
    return doors[0] if doors else None


def corpse_touched_by_ghost(ghost: Ghost, corpses: arcade.SpriteList) -> Corpse | None:
    """Cadavre touche par le fantome : c'est le point de livraison des objets."""
    touched = arcade.check_for_collision_with_list(ghost, corpses)
    return touched[0] if touched else None


def enemy_striking_player(player: Player, enemies: Iterable[Enemy]) -> Enemy | None:
    """Premier ennemi dont le coup d'epee touche le corps physique vivant.

    Le simple contact avec le corps d'un ennemi ne tue pas : seul le coup,
    pendant les frames ou la lame est tendue (`Enemy.strike_active`), compte.
    Un ennemi `DYING` n'est jamais en train de frapper.
    """
    if not player.alive:
        return None
    for enemy in enemies:
        if enemy.strike_active and enemy.strike_reaches(player):
            return enemy
    return None


def enemy_stomped_by_player(player: Player, enemies: arcade.SpriteList) -> Enemy | None:
    """Ennemi ecrase par le joueur en retombant dessus (attaque de base).

    Le seuil utilise `settings.ENEMY_HEIGHT` (hauteur du corps visible du
    squelette) plutot que `enemy.height` : ce dernier reflete desormais la
    frame d'animation entiere (96x64 px), bien plus haute que l'ennemi.
    """
    if not player.alive or player.change_y >= 0:
        return None
    for enemy in arcade.check_for_collision_with_list(player, enemies):
        if enemy.state is EnemyState.DYING:
            continue
        if player.center_y > enemy.center_y + settings.ENEMY_HEIGHT / 4:
            return enemy
    return None


def enemies_hit_by_player_attack(player: Player, enemies: arcade.SpriteList) -> list[Enemy]:
    """Retourne les ennemis recouverts par la hitbox de la frappe frontale."""
    bounds = player.attack_bounds
    if bounds is None:
        return []
    left, bottom, right, top = bounds
    return [
        enemy
        for enemy in enemies
        if enemy.state is not EnemyState.DYING
        and not player.attack_has_hit(enemy)
        and enemy.right >= left
        and enemy.left <= right
        and enemy.top >= bottom
        and enemy.bottom <= top
    ]


def plate_is_weighted(plate: arcade.Sprite, weights: Sequence[arcade.Sprite]) -> bool:
    """Un poids (corps, cadavre, ennemi) appuie-t-il sur la plaque ?"""
    return any(arcade.check_for_collision(plate, body) for body in weights)


def enemies_hit_by_falling_spikes(
    enemies: arcade.SpriteList,
    falling_spikes: arcade.SpriteList,
) -> list[Enemy]:
    """Ennemis touches par une pique en chute."""
    hit: list[Enemy] = []
    seen: set[int] = set()
    for spike in falling_spikes:
        for enemy in arcade.check_for_collision_with_list(spike, enemies):
            ident = id(enemy)
            if ident in seen:
                continue
            seen.add(ident)
            hit.append(enemy)
    return hit
