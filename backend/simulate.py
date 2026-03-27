"""
CLI Simulation Runner

Runs the Generative Agents simulation without a frontend.
Records all steps to master_movement.json for later replay.

Usage:
    python -m backend.simulate --steps 100
    python -m backend.simulate --steps 500 --output backend/data/saves/my_run
    python -m backend.simulate --steps 100 --sim the_ville --checkpoint-every 50
"""

from __future__ import annotations

import sys
import time
import argparse
import logging
import traceback
from pathlib import Path

# File-only logging (keep console clean for progress bar)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(open("/dev/null" if sys.platform != "win32" else "NUL", "w"))],
)

from backend.world_engine import WorldEngine
from backend.recorder import SimulationRecorder
from backend.config import DATA_DIR

log = logging.getLogger(__name__)


def format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


def print_progress(step: int, total: int, elapsed: float,
                   persona_name: str = "", description: str = ""):
    """Print a rich progress bar to terminal."""
    pct = step / total if total > 0 else 0
    bar_width = 30
    filled = int(bar_width * pct)
    bar = "█" * filled + "░" * (bar_width - filled)

    # ETA calculation
    if step > 0:
        eta = elapsed / step * (total - step)
        eta_str = format_time(eta)
    else:
        eta_str = "..."

    # Truncate description
    desc = description[:40] + "..." if len(description) > 40 else description

    line = (
        f"\r  {bar} {step}/{total} ({pct*100:5.1f}%) "
        f"| {format_time(elapsed)} elapsed | ETA {eta_str} "
        f"| {persona_name}: {desc}"
    )
    # Pad to clear previous line
    sys.stdout.write(line.ljust(120))
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Run Generative Agents simulation (no frontend)")
    parser.add_argument("--sim", default="the_ville",
                        help="Simulation name (default: the_ville)")
    parser.add_argument("--steps", type=int, default=100,
                        help="Number of steps to simulate")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory for saves")
    parser.add_argument("--checkpoint-every", type=int, default=50,
                        help="Save checkpoint every N steps")
    args = parser.parse_args()

    # Determine output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DATA_DIR / "saves" / f"{args.sim}_{timestamp}"

    # File logging (detailed logs go to file, not console)
    output_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        str(output_dir / "simulation.log"), encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
    logging.getLogger().addHandler(file_handler)

    # Console header
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         Generative Agents — World Simulation            ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  World:      {args.sim:<43}║")
    print(f"║  Steps:      {args.steps:<43}║")
    print(f"║  Output:     {str(output_dir)[-43:]:<43}║")
    print(f"║  Checkpoint: every {args.checkpoint_every} steps{' ' * (33 - len(str(args.checkpoint_every)))}║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Load simulation
    print("  Loading simulation...", end="", flush=True)
    engine = WorldEngine()
    engine.load_simulation(args.sim)
    recorder = SimulationRecorder(output_dir)
    print(f" OK ({len(engine.personas)} personas loaded)")
    print(f"  World time: {engine.curr_time}")
    print(f"  Logs: {output_dir / 'simulation.log'}")
    print()

    log.info("=" * 60)
    log.info("Simulation started: %s, %d steps", args.sim, args.steps)
    log.info("Output: %s", output_dir)

    # Run steps
    start_time = time.time()
    last_persona = ""
    last_desc = ""

    for i in range(args.steps):
        step_num = i + 1
        elapsed = time.time() - start_time

        print_progress(step_num, args.steps, elapsed, last_persona, last_desc)

        try:
            step_data = engine.run_step()
            recorder.record_step(step_data["step"], step_data["movements"])

            # Extract last persona info for display
            for name, mv in step_data["movements"].items():
                if mv.get("description"):
                    last_persona = name.split()[0]  # First name only
                    last_desc = mv["description"]

        except Exception as e:
            print()  # Newline after progress bar
            print(f"\n  ❌ FATAL error at step {step_num}: {e}")
            log.error("FATAL error at step %d: %s\n%s",
                      step_num, e, traceback.format_exc())
            print("  Saving progress...", end="", flush=True)
            recorder.save_all(
                args.sim,
                engine.start_time.strftime("%B %d, %Y"),
                engine.sec_per_step,
                list(engine.personas.keys()))
            engine.save(output_dir / "checkpoint")
            print(" saved.")
            sys.exit(1)

        # Periodic checkpoint
        if step_num % args.checkpoint_every == 0:
            recorder.save_all(
                args.sim,
                engine.start_time.strftime("%B %d, %Y"),
                engine.sec_per_step,
                list(engine.personas.keys()))
            engine.save(output_dir / "checkpoint")
            log.info("Checkpoint saved at step %d", step_num)

    # Final save
    total_time = time.time() - start_time
    print()  # Newline after progress bar
    print()
    print(f"  ✅ Simulation complete! ({args.steps} steps in {format_time(total_time)})")
    print(f"  Avg: {total_time / args.steps:.1f}s per step")
    print("  Saving final state...", end="", flush=True)

    recorder.save_all(
        args.sim,
        engine.start_time.strftime("%B %d, %Y"),
        engine.sec_per_step,
        list(engine.personas.keys()))
    engine.save(output_dir / "final")

    print(" done.")
    print(f"  Output: {output_dir}")
    print(f"  Replay: open frontend and select '{output_dir.name}'")
    print()

    log.info("Simulation complete: %d steps in %.1fs", args.steps, total_time)


if __name__ == "__main__":
    main()
