"""
A* Pathfinding on 2D grid.

Faithful reimplementation of the original Generative Agents path_finder.py.
"""

from __future__ import annotations

import heapq


def path_finder(collision_maze: list[list[int]],
                start: tuple[int, int],
                end: tuple[int, int],
                collision_block_id: int = 32001) -> list[tuple[int, int]]:
    """Find shortest path from start to end using A* on a tile grid.

    Args:
        collision_maze: 2D grid where non-zero values are obstacles.
        start: (x, y) start tile.
        end: (x, y) end tile.
        collision_block_id: Not used directly; any non-zero tile is blocked.

    Returns:
        List of (x, y) tiles from start to end inclusive.
        Empty list if no path found.
    """
    if start == end:
        return [start]

    if not collision_maze:
        return []

    height = len(collision_maze)
    width = len(collision_maze[0]) if height > 0 else 0

    def is_walkable(x, y):
        if 0 <= y < height and 0 <= x < width:
            return collision_maze[y][x] == 0
        return False

    if not is_walkable(end[0], end[1]):
        # Find nearest walkable tile to end
        best = end
        best_dist = float('inf')
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                nx, ny = end[0] + dx, end[1] + dy
                if is_walkable(nx, ny):
                    d = abs(dx) + abs(dy)
                    if d < best_dist:
                        best_dist = d
                        best = (nx, ny)
        end = best

    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}

    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path

        for dx, dy in directions:
            neighbor = (current[0] + dx, current[1] + dy)
            if not is_walkable(neighbor[0], neighbor[1]):
                continue

            tentative = g_score[current] + 1
            if tentative < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                f = tentative + heuristic(neighbor, end)
                heapq.heappush(open_set, (f, neighbor))

    return []  # No path found
