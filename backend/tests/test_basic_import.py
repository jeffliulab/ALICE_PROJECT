"""Basic import and data loading test."""
import sys
sys.path.insert(0, ".")

from backend.persona.memory_structures.associative_memory import ConceptNode, AssociativeMemory
from backend.persona.memory_structures.spatial_memory import MemoryTree
from backend.persona.memory_structures.scratch import Scratch
print("Memory structures: OK")

from backend.path_finder import path_finder
print("Path finder: OK")

from backend.config import DATA_DIR
print(f"DATA_DIR: {DATA_DIR}")
print(f"Data exists: {DATA_DIR.exists()}")

# Test loading scratch
s = Scratch(str(DATA_DIR / "the_ville/personas/Isabella Rodriguez/bootstrap_memory/scratch.json"))
print(f"Loaded scratch: {s.name}, age={s.age}, vision_r={s.vision_r}, decay={s.recency_decay}")
print(f"Daily plan req: {s.daily_plan_req[:60]}...")

# Test loading spatial memory
sm = MemoryTree(str(DATA_DIR / "the_ville/personas/Isabella Rodriguez/bootstrap_memory/spatial_memory.json"))
print(f"Spatial memory worlds: {list(sm.tree.keys())}")
sectors = sm.get_str_accessible_sectors("the Ville")
print(f"Accessible sectors: {sectors[:80]}...")

# Test path finder
collision = [[0]*10 for _ in range(10)]
collision[5][5] = 1
path = path_finder(collision, (0, 0), (9, 9))
print(f"Path finder test: {len(path)} steps")

# Test maze loading
from backend.maze import Maze
maze = Maze("the_ville", DATA_DIR)
print(f"Maze loaded: {maze.maze_width}x{maze.maze_height}")
print(f"Address tiles count: {len(maze.address_tiles)}")
tile_info = maze.access_tile((50, 50))
print(f"Tile (50,50): world={tile_info['world']}, sector={tile_info['sector']}, arena={tile_info['arena']}")

# Test WorldEngine
from backend.world_engine import WorldEngine
engine = WorldEngine()
engine.load_simulation("the_ville")
print(f"Engine loaded: {len(engine.personas)} personas, step={engine.step}")
print(f"Time: {engine.curr_time}")
print(f"Persona names: {list(engine.personas.keys())[:5]}...")

print("\nAll imports and basic tests passed!")
