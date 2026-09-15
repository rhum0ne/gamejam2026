"""Detection des collisions "de gameplay".

Les collisions *physiques* (joueur contre murs, gravite) sont deja gerees par
`arcade.PhysicsEnginePlatformer` dans les entites. Ce module ne s'occupe que
des chocs qui declenchent une regle de jeu : mort sur les piques, ramassage
d'un objet, ennemi qui touche le joueur, etc.

Convention : ces fonctions **ne modifient rien**, elles se contentent de
detecter et de retourner ce qui a ete touche. C'est l'appelant
(`src.systems.game_state`) qui applique les consequences. Cela rend les regles
testables sans fenetre Arcade.
"""

from __future__ import annotations

import arcade

import settings
from src.entities.corpse import Corpse
from src.entities.enemy import Enemy
from src.entities.ghost import Ghost
from src.entities.item import Item
from src.entities.player import Player
from src.world.level import Level
from src.world.obstacles import Door


def player_hits_hazard(player: Player, level: Level) -> bool:
    """Le corps physique touche-t-il un piege mortel (piques) ?"""
    return any(
        getattr(hazard, "lethal_for_body", True)
        for hazard in hazards_touched_by_player(player, level)
    )


def hazards_touched_by_player(player: Player, level: Level) -> list[arcade.Sprite]:
    """Retourne les pieges en contact avec le corps physique vivant."""
    if not player.alive:
        return []
    return arcade.check_for_collision_with_list(player, level.hazards)


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


def door_touched_by_player(player: Player, level: Level) -> Door | None:
    """Porte en contact avec le corps physique, s'il y en a une."""
    doors = arcade.check_for_collision_with_list(player, level.doors)
    return doors[0] if doors else None


def corpse_touched_by_ghost(ghost: Ghost, corpses: arcade.SpriteList) -> Corpse | None:
    """Cadavre touche par le fantome : c'est le point de livraison des objets."""
    touched = arcade.check_for_collision_with_list(ghost, corpses)
    return touched[0] if touched else None


def enemy_touching_player(player: Player, enemies: arcade.SpriteList) -> Enemy | None:
    """Premier ennemi en contact avec le corps physique vivant."""
    if not player.alive:
        return None
    touched = arcade.check_for_collision_with_list(player, enemies)
    return touched[0] if touched else None


def enemy_stomped_by_player(player: Player, enemies: arcade.SpriteList) -> Enemy | None:
    """Ennemi ecrase par le joueur en retombant dessus (attaque de base)."""
    if not player.alive or player.change_y >= 0:
        return None
    for enemy in arcade.check_for_collision_with_list(player, enemies):
        if player.center_y > enemy.center_y + enemy.height / 4:
            return enemy
    return None
