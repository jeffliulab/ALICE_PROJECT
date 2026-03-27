"""
Maze / World Map

Tile-based world representation. Loads from the original Generative Agents
CSV matrix format (collision, sector, arena, game_object, spawning layers).
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class Maze:
    def __init__(self, maze_name: str, data_dir: Path):
        self.maze_name = maze_name

        matrix_dir = data_dir / "the_ville" / "matrix"
        meta_path = matrix_dir / "maze_meta_info.json"
        meta = json.load(open(meta_path))

        self.world_name = meta["world_name"]
        self.maze_width = meta["maze_width"]
        self.maze_height = meta["maze_height"]
        self.sq_tile_size = meta["sq_tile_size"]

        # Load special blocks mappings (color_code -> address path)
        sb_dir = matrix_dir / "special_blocks"
        self.sector_blocks = self._load_special_blocks(
            sb_dir / "sector_blocks.csv")
        self.arena_blocks = self._load_special_blocks(
            sb_dir / "arena_blocks.csv")
        self.game_object_blocks = self._load_special_blocks(
            sb_dir / "game_object_blocks.csv")
        self.spawning_blocks = self._load_special_blocks(
            sb_dir / "spawning_location_blocks.csv")
        self.world_blocks = self._load_special_blocks(
            sb_dir / "world_blocks.csv")

        # Load maze layers (flattened CSV -> 2D arrays)
        maze_dir = matrix_dir / "maze"
        self.collision_maze = self._load_maze_csv(
            maze_dir / "collision_maze.csv")
        self.sector_maze = self._load_maze_csv(
            maze_dir / "sector_maze.csv")
        self.arena_maze = self._load_maze_csv(
            maze_dir / "arena_maze.csv")
        self.game_object_maze = self._load_maze_csv(
            maze_dir / "game_object_maze.csv")
        self.spawning_maze = self._load_maze_csv(
            maze_dir / "spawning_location_maze.csv")

        # Build tile info cache and address_tiles mapping
        self.tiles: list[list[dict]] = []
        self.address_tiles: dict[str, set[tuple[int, int]]] = {}
        self._build_tile_info()

        log.info("Loaded maze '%s' (%dx%d)", maze_name,
                 self.maze_width, self.maze_height)

    def _load_special_blocks(self, csv_path: Path) -> dict[int, list[str]]:
        """Load special blocks CSV: color_code, world, [sector], [arena], ..."""
        mapping = {}
        if not csv_path.exists():
            return mapping
        with open(csv_path, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                row = [c.strip() for c in row]
                if not row or not row[0]:
                    continue
                try:
                    code = int(row[0])
                    mapping[code] = row[1:]
                except ValueError:
                    continue
        return mapping

    def _load_maze_csv(self, csv_path: Path) -> list[list[int]]:
        """Load a maze CSV (single row of width*height values) into 2D array."""
        if not csv_path.exists():
            return [[0] * self.maze_width for _ in range(self.maze_height)]

        with open(csv_path, "r") as f:
            reader = csv.reader(f)
            flat = []
            for row in reader:
                for val in row:
                    val = val.strip()
                    if val:
                        try:
                            flat.append(int(val))
                        except ValueError:
                            flat.append(0)

        # Reshape to 2D: [y][x]
        grid = []
        for y in range(self.maze_height):
            row_start = y * self.maze_width
            row_end = row_start + self.maze_width
            if row_end <= len(flat):
                grid.append(flat[row_start:row_end])
            else:
                grid.append([0] * self.maze_width)
        return grid

    def _build_tile_info(self):
        """Build per-tile info and address_tiles mapping."""
        self.tiles = []
        for y in range(self.maze_height):
            row = []
            for x in range(self.maze_width):
                world = ""
                sector = ""
                arena = ""
                game_object = ""

                # Resolve world
                s_code = self.sector_maze[y][x]
                if s_code in self.sector_blocks:
                    parts = self.sector_blocks[s_code]
                    world = parts[0] if len(parts) > 0 else ""
                    sector = parts[1] if len(parts) > 1 else ""

                # Resolve arena
                a_code = self.arena_maze[y][x]
                if a_code in self.arena_blocks:
                    parts = self.arena_blocks[a_code]
                    if not world and len(parts) > 0:
                        world = parts[0]
                    if not sector and len(parts) > 1:
                        sector = parts[1]
                    arena = parts[2] if len(parts) > 2 else ""

                # Resolve game object
                go_code = self.game_object_maze[y][x]
                if go_code in self.game_object_blocks:
                    parts = self.game_object_blocks[go_code]
                    game_object = parts[-1] if parts else ""

                tile = {
                    "world": world,
                    "sector": sector,
                    "arena": arena,
                    "game_object": game_object,
                    "events": set(),
                    "x": x,
                    "y": y,
                }
                row.append(tile)

                # Build address_tiles
                if world and sector and arena:
                    if game_object:
                        addr = f"{world}:{sector}:{arena}:{game_object}"
                        self.address_tiles.setdefault(addr, set()).add((x, y))
                    addr3 = f"{world}:{sector}:{arena}"
                    self.address_tiles.setdefault(addr3, set()).add((x, y))

            self.tiles.append(row)

    def access_tile(self, tile: tuple[int, int]) -> dict:
        """Get tile info at (x, y)."""
        x, y = tile
        if 0 <= y < self.maze_height and 0 <= x < self.maze_width:
            return self.tiles[y][x]
        return {"world": "", "sector": "", "arena": "",
                "game_object": "", "events": set()}

    def get_tile_path(self, tile: tuple[int, int], level: str) -> str:
        """Get the address path at a given level (world/sector/arena)."""
        info = self.access_tile(tile)
        if level == "world":
            return info["world"]
        elif level == "sector":
            return f"{info['world']}:{info['sector']}"
        elif level == "arena":
            return f"{info['world']}:{info['sector']}:{info['arena']}"
        return ""

    def get_nearby_tiles(self, center: tuple[int, int],
                         radius: int) -> list[tuple[int, int]]:
        """Get all tiles within Manhattan distance radius."""
        cx, cy = center
        result = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.maze_width and 0 <= ny < self.maze_height:
                    result.append((nx, ny))
        return result

    def add_event_from_tile(self, event: tuple, tile: tuple[int, int]):
        """Add an event to a tile. Event format: (s, p, o, desc)."""
        info = self.access_tile(tile)
        info["events"].add(event)

    def remove_event_from_tile(self, event: tuple, tile: tuple[int, int]):
        """Remove an event from a tile."""
        info = self.access_tile(tile)
        info["events"].discard(event)

    def remove_subject_events_from_tile(self, subject: str,
                                         tile: tuple[int, int]):
        """Remove all events with the given subject from a tile."""
        info = self.access_tile(tile)
        to_remove = {ev for ev in info["events"] if ev[0] == subject}
        info["events"] -= to_remove

    def turn_event_from_tile_idle(self, event: tuple, tile: tuple[int, int]):
        """Reset an object event to idle (None predicates)."""
        info = self.access_tile(tile)
        info["events"].discard(event)
        blank = (event[0], None, None, None)
        info["events"].add(blank)
