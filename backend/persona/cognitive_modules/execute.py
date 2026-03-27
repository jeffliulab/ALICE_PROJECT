"""
Execute Module

Converts planned action address into concrete tile movement using A* pathfinding.
Handles normal navigation, persona-persona interaction, waiting, and random targets.
"""

from __future__ import annotations

import random
import logging
from typing import TYPE_CHECKING

from backend.path_finder import path_finder

if TYPE_CHECKING:
    from backend.persona.persona import Persona

log = logging.getLogger(__name__)

# Collision block identifier used by maze
COLLISION_BLOCK_ID = 32001


def execute(persona: Persona, maze, personas: dict, plan_address: str):
    """Execute the plan by computing movement path and returning next tile.

    Returns (next_tile, pronunciatio, description).
    """
    scratch = persona.scratch

    if "<random>" in (plan_address or "") and not scratch.planned_path:
        scratch.act_path_set = False

    if not scratch.act_path_set:
        target_tiles = None

        if plan_address and "<persona>" in plan_address:
            target_name = plan_address.split("<persona>")[-1].strip()
            if target_name in personas:
                target_p_tile = personas[target_name].scratch.curr_tile
                potential_path = path_finder(
                    maze.collision_maze, scratch.curr_tile,
                    target_p_tile, COLLISION_BLOCK_ID)
                if len(potential_path) <= 2:
                    target_tiles = [potential_path[0]]
                else:
                    mid = len(potential_path) // 2
                    target_tiles = [potential_path[mid]]

        elif plan_address and "<waiting>" in plan_address:
            parts = plan_address.split()
            x = int(parts[1])
            y = int(parts[2])
            target_tiles = [(x, y)]

        elif plan_address and "<random>" in plan_address:
            clean_addr = ":".join(plan_address.split(":")[:-1])
            if clean_addr in maze.address_tiles:
                tiles = list(maze.address_tiles[clean_addr])
                target_tiles = random.sample(tiles, min(1, len(tiles)))

        elif plan_address and plan_address in maze.address_tiles:
            target_tiles = list(maze.address_tiles[plan_address])

        if target_tiles is None:
            # Fallback: stay in place
            scratch.act_path_set = True
            scratch.planned_path = []
        else:
            # Sample a few target tiles
            if len(target_tiles) > 4:
                target_tiles = random.sample(target_tiles, 4)

            # Prefer unoccupied tiles
            persona_names = set(personas.keys())
            new_targets = []
            for t in target_tiles:
                tile_events = maze.access_tile(t)["events"]
                occupied = any(ev[0] in persona_names for ev in tile_events)
                if not occupied:
                    new_targets.append(t)
            if not new_targets:
                new_targets = target_tiles
            target_tiles = new_targets

            # Find shortest path to closest target
            curr_tile = scratch.curr_tile
            best_path = None
            for t in target_tiles:
                p = path_finder(maze.collision_maze, curr_tile,
                                t, COLLISION_BLOCK_ID)
                if p and (best_path is None or len(p) < len(best_path)):
                    best_path = p

            if best_path:
                scratch.planned_path = best_path[1:]  # exclude current tile
            else:
                scratch.planned_path = []
            scratch.act_path_set = True

    # Take one step
    ret = scratch.curr_tile
    if scratch.planned_path:
        ret = scratch.planned_path[0]
        scratch.planned_path = scratch.planned_path[1:]

    description = f"{scratch.act_description}"
    if scratch.act_address:
        description += f" @ {scratch.act_address}"

    return ret, scratch.act_pronunciatio or "🙂", description
