"""
Simulation Recorder

Records each step's movement data to master_movement.json
for later replay in the frontend. Compatible with the original
paper's compressed_storage format.
"""

from __future__ import annotations

import json
import logging
import datetime
from pathlib import Path

log = logging.getLogger(__name__)


class SimulationRecorder:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.movements: dict[str, dict] = {}

    def record_step(self, step: int, movements: dict):
        """Record one step's movement data."""
        self.movements[str(step)] = movements

    def save_movements(self):
        """Save all recorded movements to master_movement.json."""
        path = self.output_dir / "master_movement.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.movements, f, ensure_ascii=False)
        log.info("Saved %d steps to %s", len(self.movements), path)

    def save_meta(self, sim_name: str, start_date: str, sec_per_step: int,
                  persona_names: list[str], total_steps: int):
        """Save simulation metadata."""
        meta = {
            "sim_name": sim_name,
            "start_date": start_date,
            "sec_per_step": sec_per_step,
            "persona_names": persona_names,
            "total_steps": total_steps,
            "created_at": datetime.datetime.now().isoformat(),
        }
        path = self.output_dir / "meta.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        log.info("Saved meta to %s", path)

    def save_all(self, sim_name: str, start_date: str, sec_per_step: int,
                 persona_names: list[str]):
        """Save both movements and metadata."""
        self.save_movements()
        self.save_meta(sim_name, start_date, sec_per_step,
                       persona_names, len(self.movements))
