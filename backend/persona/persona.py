"""
Persona (Generative Agent)

Main agent class implementing the cognitive loop:
  perceive -> retrieve -> plan -> reflect -> execute

Faithful reimplementation of the original Generative Agents persona.py.
"""

from __future__ import annotations

import logging

from backend.persona.memory_structures.spatial_memory import MemoryTree
from backend.persona.memory_structures.associative_memory import AssociativeMemory
from backend.persona.memory_structures.scratch import Scratch

from backend.persona.cognitive_modules.perceive import perceive
from backend.persona.cognitive_modules.retrieve import retrieve
from backend.persona.cognitive_modules.plan import plan
from backend.persona.cognitive_modules.reflect import reflect
from backend.persona.cognitive_modules.execute import execute

log = logging.getLogger(__name__)


class Persona:
    def __init__(self, name: str, folder_mem_saved: str):
        self.name = name

        f_s_mem = f"{folder_mem_saved}/bootstrap_memory/spatial_memory.json"
        self.s_mem = MemoryTree(f_s_mem)

        f_a_mem = f"{folder_mem_saved}/bootstrap_memory/associative_memory"
        self.a_mem = AssociativeMemory(f_a_mem)

        f_scratch = f"{folder_mem_saved}/bootstrap_memory/scratch.json"
        self.scratch = Scratch(f_scratch)

    def save(self, save_folder: str):
        f_s_mem = f"{save_folder}/spatial_memory.json"
        self.s_mem.save(f_s_mem)

        f_a_mem = f"{save_folder}/associative_memory"
        self.a_mem.save(f_a_mem)

        f_scratch = f"{save_folder}/scratch.json"
        self.scratch.save(f_scratch)

    def move(self, maze, personas: dict, curr_tile: tuple, curr_time):
        """Main cognitive loop — called once per simulation step.

        Returns (next_tile, pronunciatio, description).
        """
        self.scratch.curr_tile = curr_tile

        # Detect new day
        new_day = False
        if not self.scratch.curr_time:
            new_day = "First day"
        elif (self.scratch.curr_time.strftime('%A %B %d')
              != curr_time.strftime('%A %B %d')):
            new_day = "New day"
        self.scratch.curr_time = curr_time

        if new_day:
            log.info("  %s: %s", self.name, new_day)

        # 1. Perceive
        log.info("  %s: perceive...", self.name)
        perceived = perceive(self, maze)
        log.info("  %s: perceived %d events", self.name, len(perceived))

        # 2. Retrieve
        log.info("  %s: retrieve...", self.name)
        retrieved = retrieve(self, perceived)
        log.info("  %s: retrieved %d focal points", self.name, len(retrieved))

        # 3. Plan
        log.info("  %s: plan...", self.name)
        act_address = plan(self, maze, personas, new_day, retrieved)
        log.info("  %s: plan -> %s | %s", self.name,
                 act_address, self.scratch.act_description)

        # 4. Reflect
        log.info("  %s: reflect...", self.name)
        reflect(self)

        # 5. Execute
        log.info("  %s: execute...", self.name)
        result = execute(self, maze, personas, act_address)
        log.info("  %s: execute -> tile %s", self.name, result[0])
        return result
