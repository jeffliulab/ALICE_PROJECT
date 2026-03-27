"""
Spatial Memory (MemoryTree)

Hierarchical tree: world -> sector -> arena -> [game_objects]
Faithfully reimplements the original Generative Agents spatial_memory.py.
"""

import json
from pathlib import Path


class MemoryTree:
    def __init__(self, f_saved: str):
        self.tree: dict = {}
        if Path(f_saved).exists():
            self.tree = json.load(open(f_saved))

    def save(self, out_json: str):
        with open(out_json, "w") as f:
            json.dump(self.tree, f)

    def get_str_accessible_sectors(self, curr_world: str) -> str:
        if curr_world not in self.tree:
            return ""
        return ", ".join(list(self.tree[curr_world].keys()))

    def get_str_accessible_sector_arenas(self, sector: str) -> str:
        curr_world, curr_sector = sector.split(":")
        if not curr_sector or curr_world not in self.tree:
            return ""
        if curr_sector not in self.tree.get(curr_world, {}):
            return ""
        return ", ".join(list(self.tree[curr_world][curr_sector].keys()))

    def get_str_accessible_arena_game_objects(self, arena: str) -> str:
        parts = arena.split(":")
        if len(parts) < 3:
            return ""
        curr_world, curr_sector, curr_arena = parts[0], parts[1], parts[2]
        if not curr_arena:
            return ""
        try:
            return ", ".join(
                list(self.tree[curr_world][curr_sector][curr_arena]))
        except KeyError:
            try:
                return ", ".join(
                    list(self.tree[curr_world][curr_sector][curr_arena.lower()]))
            except KeyError:
                return ""
