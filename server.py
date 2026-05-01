"""
Bombardment Engine — FastAPI Server
====================================
Serves the real-time dashboard and exposes:
  • WebSocket /ws         — live stats + crash event stream
  • POST     /api/analyze — call Gemini to select algorithms
  • POST     /api/start   — start the fuzzer (with selected algos)
  • POST     /api/stop    — stop the fuzzer
  • GET      /api/stats   — current snapshot
  • GET      /api/crashes — list crash log files
"""

import os
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from engine.orchestrator import Orchestrator
from engine.strategy_analyzer import analyze_target

# ── paths ───────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
TARGET = str(BASE_DIR / "target" / "vulnerable")
SEED_DIR = str(BASE_DIR / "seeds")
CRASH_DIR = str(BASE_DIR / "crash_logs")
FRONTEND_DIR = str(BASE_DIR / "frontend")

# ── state ───────────────────────────────────────────────────────
orchestrator: Orchestrator | None = None
fuzz_task: asyncio.Task | None = None
connected_clients: list[WebSocket] = []
last_analysis: dict | None = None  # cache Gemini's response


# ── WebSocket broadcaster ──────────────────────────────────────
async def broadcast(msg_type: str, data: dict):
    payload = json.dumps({"type": msg_type, "data": data})
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in connected_clients:
            connected_clients.remove(ws)


async def on_crash(event: dict):
    await broadcast("crash_event", event)


async def on_stats(stats: dict):
    await broadcast("stats_update", stats)


# ── app ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(CRASH_DIR, exist_ok=True)
    yield
    global orchestrator, fuzz_task
    if orchestrator:
        orchestrator.stop()
    if fuzz_task and not fuzz_task.done():
        fuzz_task.cancel()


app = FastAPI(title="Bombardment Engine", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ── routes ──────────────────────────────────────────────────────
@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in connected_clients:
            connected_clients.remove(ws)


# ── Gemini Analysis ────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    custom_description: Optional[str] = None


@app.post("/api/analyze")
async def analyze_endpoint(req: AnalyzeRequest = AnalyzeRequest()):
    global last_analysis

    await broadcast("log_message", {"message": "🧠 Sending target to Gemini 2.5 Flash for strategy analysis..."})

    result = await analyze_target(
        target_binary=TARGET,
        seed_dir=SEED_DIR,
        custom_description=req.custom_description,
    )
    last_analysis = result

    await broadcast("analysis_result", result)
    await broadcast("log_message", {
        "message": f"🧠 Gemini selected: {', '.join(result['selected_algorithms'])} ({result['status']})"
    })

    return result


# ── Start / Stop ────────────────────────────────────────────────
class StartRequest(BaseModel):
    algorithms: Optional[list[str]] = None


@app.post("/api/start")
async def start_fuzzing(req: StartRequest = StartRequest()):
    global orchestrator, fuzz_task

    if fuzz_task and not fuzz_task.done():
        return {"status": "already_running"}

    if not os.path.isfile(TARGET):
        return {
            "status": "error",
            "message": f"Target binary not found at {TARGET}. "
                       "Compile with: clang++ -o target/vulnerable -fno-stack-protector -O0 target/vulnerable.cpp",
        }

    # Use algorithms from request, or from last analysis, or all
    algos = req.algorithms
    if not algos and last_analysis:
        algos = last_analysis.get("selected_algorithms")
    if not algos:
        algos = ["bit_flip", "arithmetic", "block", "dictionary"]

    orchestrator = Orchestrator(
        target_binary=TARGET,
        seed_dir=SEED_DIR,
        crash_dir=CRASH_DIR,
        timeout=2.0,
        active_algorithms=algos,
    )
    orchestrator.set_callbacks(on_crash=on_crash, on_stats=on_stats)
    fuzz_task = asyncio.create_task(orchestrator.run())

    await broadcast("log_message", {
        "message": f"🚀 Bombardment started with algorithms: {', '.join(algos)}"
    })
    return {"status": "started", "algorithms": algos}


@app.post("/api/stop")
async def stop_fuzzing():
    global orchestrator, fuzz_task

    if not orchestrator or not fuzz_task or fuzz_task.done():
        return {"status": "not_running"}

    orchestrator.stop()
    await broadcast("log_message", {"message": "🛑 Bombardment engine stopped."})

    if orchestrator:
        await broadcast("stats_update", orchestrator.stats.to_dict())

    return {"status": "stopped"}


@app.get("/api/stats")
async def get_stats():
    if orchestrator:
        return orchestrator.stats.to_dict()
    return {"total_iterations": 0, "crashes_found": 0}


@app.get("/api/crashes")
async def get_crashes():
    files = []
    if os.path.isdir(CRASH_DIR):
        for f in sorted(os.listdir(CRASH_DIR)):
            fpath = os.path.join(CRASH_DIR, f)
            files.append({"name": f, "size": os.path.getsize(fpath)})
    return {"crashes": files}


@app.get("/api/seeds")
async def get_seeds():
    if orchestrator:
        return {"seeds": orchestrator.seed_pool.summary()}
    return {"seeds": []}
