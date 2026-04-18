"""
demo_app.py — Hackathon Pitch Server (TEMPORARY)
=================================================
Run this INSTEAD OF server/app.py on demo day:

    python server/demo_app.py

It starts the full OpenEnv environment on port 8080 AND serves the
interactive frontend at http://localhost:8080/

After the hackathon, delete:
  - server/demo_app.py   (this file)
  - public/              (the frontend)

The core OpenEnv submission (server/app.py, inference.py, etc.) is
completely untouched and safe for evaluation.
"""

import pathlib
import traceback
import uvicorn

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles

# ── Re-use the fully configured OpenEnv app + router ──────────────────────
# server/app.py registers all OpenEnv routes (reset, step, grader, baseline)
# on `app`. We just bolt on two things: the demo endpoint + static file mount.
from server.app import app          # the real OpenEnv FastAPI instance


# ── /api/demo/{task_id} ───────────────────────────────────────────────────
@app.post("/api/demo/{task_id}", tags=["Demo"])
def run_demo_task(task_id: str, use_llm: bool = False):
    """
    **Hackathon Demo Endpoint** — runs the baseline agent on one task and
    returns the full step-by-step execution trace for the live dashboard.

    - **task_id** : `t1` | `t2` | `t3`
    - **use_llm** : `false` → fast deterministic baseline (default for demo)
                    `true`  → calls LLM via HF_TOKEN (slower, requires .env)
    """
    if task_id not in ("t1", "t2", "t3"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task_id '{task_id}'. Must be t1, t2, or t3."
        )
    try:
        from inference import run_task          # lazy — keeps startup fast
        result = run_task(task_id, use_llm=use_llm, return_trace=True)
        return result
    except ImportError as e:
        raise HTTPException(
            status_code=501,
            detail=f"inference.py or a dependency is missing: {e}"
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Static file mount (public/) ───────────────────────────────────────────
# Must be registered AFTER all API routes so it doesn't shadow them.
_PUBLIC_DIR = pathlib.Path(__file__).parent.parent / "public"

if not _PUBLIC_DIR.is_dir():
    print(
        f"[demo_app] WARNING: '{_PUBLIC_DIR}' not found. "
        "The web dashboard will not be served."
    )
else:
    app.mount(
        "/",
        StaticFiles(directory=str(_PUBLIC_DIR), html=True),
        name="static",
    )
    print(f"[demo_app] Serving frontend from  {_PUBLIC_DIR}")


# ── Entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  CRM Pipeline Agent - Hackathon Demo Server")
    print("  Dashboard : http://localhost:8080/")
    print("  API docs  : http://localhost:8080/docs")
    print("=" * 60 + "\n")
    uvicorn.run(
        "server.demo_app:app",
        host="0.0.0.0",
        port=8080,
        reload=False,       # keep deterministic for the live pitch
    )
