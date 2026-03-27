"""
FastAPI Server

Main entry point for the Generative Agents simulation.
Provides REST API + WebSocket for the frontend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
import threading
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.world_engine import WorldEngine
from backend.config import DATA_DIR

# Setup logging to both console and file
_log_dir = Path(__file__).resolve().parent.parent / "logs"
_log_dir.mkdir(exist_ok=True)
_log_file = _log_dir / "simulation.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(_log_file), encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)
log.info("Log file: %s", _log_file)

app = FastAPI(title="Generative Agents Simulation", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = WorldEngine()


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        self._loop = asyncio.get_event_loop()

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                pass

    def broadcast_sync(self, data: dict):
        loop = self._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(data), loop)


ws_manager = ConnectionManager()


# ---------- REST Endpoints ----------

class StartRequest(BaseModel):
    sim_name: str = "the_ville"


@app.post("/api/start")
async def start_simulation(req: StartRequest):
    try:
        engine.load_simulation(req.sim_name)
        return {
            "status": "started",
            "personas": list(engine.personas.keys()),
            "map": {"width": engine.maze.maze_width,
                    "height": engine.maze.maze_height},
            "time": engine.curr_time.strftime("%B %d, %Y, %H:%M:%S"),
            "step": engine.step,
        }
    except Exception as e:
        log.error("Failed to start: %s", traceback.format_exc())
        return {"error": str(e)}


class StepRequest(BaseModel):
    n_steps: int = 1


@app.post("/api/step")
async def run_steps(req: StepRequest):
    if engine.running:
        return {"status": "already_running"}

    def _run():
        for i in range(req.n_steps):
            ws_manager.broadcast_sync({
                "type": "step_start",
                "data": {"step_index": i, "total_steps": req.n_steps,
                         "step_number": engine.step},
            })
            try:
                step_data = engine.run_step()
            except Exception as e:
                log.error("Step error: %s", traceback.format_exc())
                ws_manager.broadcast_sync({
                    "type": "step_error", "data": {"error": str(e)}})
                return
            ws_manager.broadcast_sync({
                "type": "step_done", "data": step_data})

        ws_manager.broadcast_sync({
            "type": "all_steps_done", "data": engine.get_state()})

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "n_steps": req.n_steps}


@app.get("/api/state")
async def get_state():
    return engine.get_state()


@app.get("/api/persona/{name}")
async def get_persona(name: str):
    persona = engine.personas.get(name)
    if not persona:
        return {"error": f"Persona '{name}' not found"}
    return {
        "name": persona.name,
        "age": persona.scratch.age,
        "innate": persona.scratch.innate,
        "learned": persona.scratch.learned,
        "currently": persona.scratch.currently,
        "lifestyle": persona.scratch.lifestyle,
        "tile": list(engine.personas_tile.get(name, (0, 0))),
        "action": persona.scratch.act_description,
        "daily_plan": persona.scratch.daily_req,
        "schedule": persona.scratch.f_daily_schedule,
    }


@app.get("/api/map")
async def get_map():
    if not engine.maze:
        return {"error": "No maze loaded"}
    return {
        "width": engine.maze.maze_width,
        "height": engine.maze.maze_height,
        "world_name": engine.maze.world_name,
        "address_tiles": {k: [list(t) for t in v]
                          for k, v in engine.maze.address_tiles.items()},
        "persona_tiles": {k: list(v) for k, v in engine.personas_tile.items()},
    }


class SaveRequest(BaseModel):
    save_name: str = "default"


@app.post("/api/save")
async def save_simulation(req: SaveRequest):
    try:
        save_dir = DATA_DIR / "saves" / req.save_name
        engine.save(save_dir)
        return {"status": "saved", "path": str(save_dir)}
    except Exception as e:
        log.error("Save error: %s", traceback.format_exc())
        return {"error": str(e)}


@app.get("/api/logs")
async def get_logs():
    """Return last 100 lines of log file for frontend debugging."""
    try:
        lines = _log_file.read_text(encoding="utf-8").splitlines()
        return {"lines": lines[-100:]}
    except Exception:
        return {"lines": []}


# ---------- Replay API ----------

@app.get("/api/replays")
async def list_replays():
    """List all saved simulation recordings."""
    saves_dir = DATA_DIR / "saves"
    if not saves_dir.exists():
        return []
    replays = []
    for d in sorted(saves_dir.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if meta_path.exists():
            try:
                meta = json.load(open(meta_path, encoding="utf-8"))
                meta["name"] = d.name
                replays.append(meta)
            except Exception:
                pass
    return replays


@app.get("/api/replay/{name}/meta")
async def get_replay_meta(name: str):
    """Get metadata for a saved simulation."""
    path = DATA_DIR / "saves" / name / "meta.json"
    if not path.exists():
        return {"error": f"Replay '{name}' not found"}
    return json.load(open(path, encoding="utf-8"))


@app.get("/api/replay/{name}/movements")
async def get_replay_movements(name: str):
    """Get all movement data for replay."""
    path = DATA_DIR / "saves" / name / "master_movement.json"
    if not path.exists():
        return {"error": f"Replay '{name}' movements not found"}
    return json.load(open(path, encoding="utf-8"))


# ---------- WebSocket ----------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "state":
                await ws.send_json({"type": "state",
                                    "data": engine.get_state()})
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=5000, reload=True)
