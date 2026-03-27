"""
World Engine (Reverie Server)

Central simulation controller. Manages the world clock, personas, and
the main simulation loop. Faithful reimplementation of reverie.py.
"""

from __future__ import annotations

import json
import logging
import datetime
import traceback
from pathlib import Path
from typing import Optional

from backend.config import DATA_DIR
from backend.maze import Maze
from backend.persona.persona import Persona

log = logging.getLogger(__name__)


class WorldEngine:
    def __init__(self):
        self.maze: Optional[Maze] = None
        self.personas: dict[str, Persona] = {}
        self.personas_tile: dict[str, tuple[int, int]] = {}

        self.start_time: Optional[datetime.datetime] = None
        self.curr_time: Optional[datetime.datetime] = None
        self.sec_per_step: int = 10
        self.step: int = 0
        self.sim_code: str = ""

        self.running = False

    def load_simulation(self, sim_name: str = "the_ville"):
        """Load a simulation from data directory."""
        self.running = False  # Reset in case of reload

        sim_dir = DATA_DIR / sim_name
        meta_path = sim_dir / "meta.json"

        with open(meta_path, "r") as f:
            meta = json.load(f)

        self.sim_code = meta.get("fork_sim_code", sim_name)
        self.start_time = datetime.datetime.strptime(
            f"{meta['start_date']}, 00:00:00", "%B %d, %Y, %H:%M:%S")
        self.curr_time = datetime.datetime.strptime(
            meta['curr_time'], "%B %d, %Y, %H:%M:%S")
        self.sec_per_step = meta.get('sec_per_step', 10)
        self.step = meta.get('step', 0)

        # Load maze
        self.maze = Maze(meta['maze_name'], DATA_DIR)

        # Load initial environment (persona positions)
        env_path = sim_dir / "environment" / "0.json"
        init_env = {}
        if env_path.exists():
            init_env = json.load(open(env_path))

        # Load personas
        self.personas = {}
        self.personas_tile = {}
        for persona_name in meta['persona_names']:
            persona_folder = str(sim_dir / "personas" / persona_name)
            persona = Persona(persona_name, persona_folder)
            self.personas[persona_name] = persona

            if persona_name in init_env:
                x = init_env[persona_name]["x"]
                y = init_env[persona_name]["y"]
                self.personas_tile[persona_name] = (x, y)

        log.info("Loaded simulation '%s': %d personas, step=%d, time=%s",
                 sim_name, len(self.personas), self.step,
                 self.curr_time.strftime("%B %d, %Y, %H:%M:%S"))

    def run_step(self) -> dict:
        """Execute one simulation step for all personas."""
        self.running = True
        try:
            return self._run_step_inner()
        except Exception as e:
            log.error("FATAL step error: %s\n%s", e, traceback.format_exc())
            raise
        finally:
            self.running = False

    def _run_step_inner(self) -> dict:
        log.info("========== STEP %d | %s ==========",
                 self.step, self.curr_time.strftime("%H:%M:%S"))

        movements = {}
        persona_names = list(self.personas.keys())
        total = len(persona_names)

        for idx, persona_name in enumerate(persona_names):
            persona = self.personas[persona_name]
            curr_tile = self.personas_tile.get(persona_name, (0, 0))

            log.info("[%d/%d] %s at tile %s", idx + 1, total,
                     persona_name, curr_tile)

            try:
                next_tile, pronunciatio, description = persona.move(
                    self.maze, self.personas, curr_tile, self.curr_time)
                log.info("  -> moved to %s | %s | %s",
                         next_tile, pronunciatio, description[:60])
            except Exception as e:
                log.error("  ERROR in %s.move(): %s\n%s",
                          persona_name, e, traceback.format_exc())
                next_tile = curr_tile
                pronunciatio = "⚠️"
                description = f"{persona_name} is confused"

            self.personas_tile[persona_name] = next_tile

            movements[persona_name] = {
                "movement": list(next_tile),
                "pronunciatio": pronunciatio,
                "description": description,
                "chat": persona.scratch.chat,
            }

        # Advance time
        self.step += 1
        self.curr_time += datetime.timedelta(seconds=self.sec_per_step)

        log.info("Step %d complete. Time now: %s",
                 self.step, self.curr_time.strftime("%H:%M:%S"))

        return {
            "step": self.step,
            "time": self.curr_time.strftime("%B %d, %Y, %H:%M:%S"),
            "movements": movements,
        }

    def get_state(self) -> dict:
        return {
            "step": self.step,
            "time": (self.curr_time.strftime("%B %d, %Y, %H:%M:%S")
                     if self.curr_time else None),
            "running": self.running,
            "personas": {
                name: {
                    "tile": list(self.personas_tile.get(name, (0, 0))),
                    "name": p.scratch.name,
                    "currently": p.scratch.currently,
                    "action": p.scratch.act_description,
                    "emoji": p.scratch.act_pronunciatio,
                }
                for name, p in self.personas.items()
            },
            "map": {
                "width": self.maze.maze_width if self.maze else 0,
                "height": self.maze.maze_height if self.maze else 0,
            },
        }

    def save(self, save_dir: Path):
        """Save full simulation state."""
        save_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "fork_sim_code": self.sim_code,
            "start_date": self.start_time.strftime("%B %d, %Y"),
            "curr_time": self.curr_time.strftime("%B %d, %Y, %H:%M:%S"),
            "sec_per_step": self.sec_per_step,
            "maze_name": self.maze.maze_name if self.maze else "",
            "persona_names": list(self.personas.keys()),
            "step": self.step,
        }
        reverie_dir = save_dir / "reverie"
        reverie_dir.mkdir(parents=True, exist_ok=True)
        with open(reverie_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

        for persona_name, persona in self.personas.items():
            persona_save_dir = str(save_dir / "personas" / persona_name
                                   / "bootstrap_memory")
            persona.save(persona_save_dir)

        env_dir = save_dir / "environment"
        env_dir.mkdir(parents=True, exist_ok=True)
        env = {name: {"maze": self.maze.maze_name if self.maze else "",
                       "x": tile[0], "y": tile[1]}
               for name, tile in self.personas_tile.items()}
        with open(env_dir / f"{self.step}.json", "w") as f:
            json.dump(env, f, indent=2)

        log.info("Saved simulation to %s (step %d)", save_dir, self.step)
