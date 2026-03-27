import { useState, useEffect, useRef, useCallback } from 'react';
import Phaser from 'phaser';
import { GameScene } from './GameScene';
import {
  listReplays, getReplayMovements, startSimulation, getState,
} from './api';
import type { ReplayMeta, StepMovements } from './api';
import './app.css';

export default function App() {
  const gameRef = useRef<Phaser.Game | null>(null);
  const sceneRef = useRef<GameScene | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Replay state
  const [replays, setReplays] = useState<ReplayMeta[]>([]);
  const [selectedReplay, setSelectedReplay] = useState<string | null>(null);
  const [replayData, setReplayData] = useState<Record<string, StepMovements> | null>(null);
  const [replayMeta, setReplayMeta] = useState<ReplayMeta | null>(null);
  const [totalSteps, setTotalSteps] = useState(0);

  // Playback state
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(2);
  const playRef = useRef(false);

  // UI state
  const [events, setEvents] = useState<string[]>([]);
  const [, setLoading] = useState(false);
  const [personaNames, setPersonaNames] = useState<string[]>([]);

  // Initialize Phaser
  useEffect(() => {
    if (!containerRef.current || gameRef.current) return;
    const scene = new GameScene();
    sceneRef.current = scene;
    const game = new Phaser.Game({
      type: Phaser.AUTO,
      width: 960,
      height: 640,
      parent: containerRef.current,
      scene: [scene],
      pixelArt: true,
      backgroundColor: '#2d5a27',
      scale: { mode: Phaser.Scale.RESIZE, autoCenter: Phaser.Scale.CENTER_BOTH },
    });
    gameRef.current = game;
    return () => { game.destroy(true); gameRef.current = null; };
  }, []);

  // Load replay list on mount
  useEffect(() => {
    listReplays().then(setReplays).catch(() => {});
  }, []);

  // Load a replay
  const loadReplay = useCallback(async (name: string) => {
    setLoading(true);
    setIsPlaying(false);
    playRef.current = false;
    setCurrentStep(0);
    setEvents([]);

    try {
      // Init the simulation to get persona positions on map
      await startSimulation('the_ville');
      const state = await getState();

      // Place personas on map
      if (sceneRef.current && state.personas) {
        for (const [pname, p] of Object.entries(state.personas) as any) {
          sceneRef.current.addPersona(pname, p.tile[0], p.tile[1], p.emoji || '🙂');
        }
        setPersonaNames(Object.keys(state.personas));
      }

      // Load movement data
      const movements = await getReplayMovements(name);
      if ((movements as any).error) {
        alert((movements as any).error);
        setLoading(false);
        return;
      }

      const meta = replays.find(r => r.name === name);
      setReplayData(movements);
      setReplayMeta(meta || null);
      setSelectedReplay(name);
      setTotalSteps(Object.keys(movements).length);
      setEvents([`Loaded replay: ${name} (${Object.keys(movements).length} steps)`]);
    } catch (e: any) {
      alert('Failed to load replay: ' + e.message);
    }
    setLoading(false);
  }, [replays]);

  // Playback timer
  useEffect(() => {
    if (!isPlaying || !replayData) return;
    playRef.current = true;

    const interval = setInterval(() => {
      if (!playRef.current) return;

      setCurrentStep(prev => {
        const next = prev + 1;
        const stepData = replayData[String(next)];

        if (!stepData) {
          // Reached end
          playRef.current = false;
          setIsPlaying(false);
          return prev;
        }

        // Update Phaser positions
        if (sceneRef.current) {
          for (const [name, mv] of Object.entries(stepData)) {
            sceneRef.current.movePersona(name, mv.movement[0], mv.movement[1], mv.pronunciatio);
          }
        }

        // Update event log
        const newEvents: string[] = [];
        for (const [name, mv] of Object.entries(stepData)) {
          if (mv.description) newEvents.push(`[Step ${next}] ${name}: ${mv.description}`);
          if (mv.chat) {
            for (const turn of mv.chat) {
              newEvents.push(`  💬 ${turn[0]}: ${turn[1]}`);
            }
          }
        }
        if (newEvents.length > 0) {
          setEvents(prev => [...newEvents, ...prev].slice(0, 300));
        }

        return next;
      });
    }, 1000 / playSpeed);

    return () => { clearInterval(interval); playRef.current = false; };
  }, [isPlaying, playSpeed, replayData]);

  // Seek to specific step
  const seekTo = useCallback((step: number) => {
    if (!replayData || !sceneRef.current) return;
    setCurrentStep(step);

    // Apply all movements up to this step to get correct positions
    // (find the latest position for each persona)
    const positions: Record<string, StepMovements[string]> = {};
    for (let s = 0; s <= step; s++) {
      const data = replayData[String(s)];
      if (data) {
        for (const [name, mv] of Object.entries(data)) {
          positions[name] = mv;
        }
      }
    }
    for (const [name, mv] of Object.entries(positions)) {
      sceneRef.current.movePersona(name, mv.movement[0], mv.movement[1], mv.pronunciatio);
    }
  }, [replayData]);

  // No replay selected — show replay picker
  if (!selectedReplay) {
    return (
      <div className="app">
        <header className="header">
          <h1>Generative Agents — Replay Viewer</h1>
        </header>
        <div className="replay-picker">
          <h2>Select a Simulation to Replay</h2>
          {replays.length === 0 ? (
            <div className="no-replays">
              <p>No saved simulations found.</p>
              <p>Run a simulation first:</p>
              <code>python -m backend.simulate --steps 100</code>
            </div>
          ) : (
            <div className="replay-list">
              {replays.map(r => (
                <div key={r.name} className="replay-card" onClick={() => loadReplay(r.name)}>
                  <h3>{r.name}</h3>
                  <p>{r.total_steps} steps | {r.persona_names?.length || '?'} agents</p>
                  <p className="meta">{r.start_date} | {r.created_at?.slice(0, 19)}</p>
                </div>
              ))}
            </div>
          )}
          <button className="refresh-btn" onClick={() => listReplays().then(setReplays)}>
            🔄 Refresh
          </button>
        </div>
      </div>
    );
  }

  // Replay loaded — show player
  return (
    <div className="app">
      <header className="header">
        <h1>Generative Agents — {selectedReplay}</h1>
        <div className="controls">
          <button onClick={() => { setSelectedReplay(null); setReplayData(null); }}>
            📂 Change
          </button>
          <button onClick={() => seekTo(Math.max(0, currentStep - 10))}>⏪</button>
          <button onClick={() => {
            if (isPlaying) { setIsPlaying(false); playRef.current = false; }
            else setIsPlaying(true);
          }}>
            {isPlaying ? '⏸️ Pause' : '▶️ Play'}
          </button>
          <button onClick={() => seekTo(Math.min(totalSteps - 1, currentStep + 10))}>⏩</button>
          <select value={playSpeed} onChange={e => setPlaySpeed(Number(e.target.value))}>
            <option value={1}>1x</option>
            <option value={2}>2x</option>
            <option value={5}>5x</option>
            <option value={10}>10x</option>
            <option value={20}>20x</option>
          </select>
        </div>
        <div className="status">
          Step {currentStep} / {totalSteps}
          {replayMeta && ` | ${replayMeta.persona_names?.length} agents`}
        </div>
      </header>

      <div className="progress-bar">
        <input
          type="range"
          min={0}
          max={totalSteps - 1}
          value={currentStep}
          onChange={e => seekTo(Number(e.target.value))}
        />
      </div>

      <div className="main">
        <div className="game-container" ref={containerRef} />
        <aside className="sidebar">
          <div className="persona-list">
            <h3>Residents ({personaNames.length})</h3>
            {personaNames.map(name => (
              <div key={name} className="persona-item">
                <span className="emoji">🙂</span>
                <div><div className="name">{name}</div></div>
              </div>
            ))}
          </div>
          <div className="event-log">
            <h3>Event Log</h3>
            <div className="log-entries">
              {events.map((e, i) => <div key={i} className="log-entry">{e}</div>)}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
