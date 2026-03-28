from fastapi import APIRouter, HTTPException

try:
    from openenv.core.env_server import create_fastapi_app
except ImportError:
    from fastapi import FastAPI
    def create_fastapi_app(env_cls, act_cls=None, obs_cls=None): return FastAPI()

import yaml
import server.environment as env_mod
print(f"DEBUG: env_mod path: {env_mod.__file__}")

from server.environment import CRMDataPipelineEnv, GLOBAL_TRUTH_STORE, GLOBAL_ENV_STORE
from server.graders import get_grader, evaluate_dataframes
from models import CRMPipelineAction, CRMPipelineObservation

app = create_fastapi_app(CRMDataPipelineEnv, CRMPipelineAction, CRMPipelineObservation)
router = APIRouter()

# ---------------------------------------------------------------------------
# /tasks  — static task catalogue
# ---------------------------------------------------------------------------
@router.get("/tasks")
def list_tasks():
    with open("openenv.yaml", "r") as f:
        config = yaml.safe_load(f)
        return {
            "tasks": config.get("tasks", []),
            "action_schema": {
                "action_type": "string",
                "source": "string",
                "column": "string",
                "standardization_strategy": "string",
                "deduplication_strategy": "string",
                "final_source": "string"
            }
        }

# ---------------------------------------------------------------------------
# /grader/{episode_id}  — grade a completed episode
# Uses the truth snapshot stored at reset() time, keyed by episode_id.
# Works across concurrent agents — no global env pointer needed.
# ---------------------------------------------------------------------------
@router.post("/grader/{episode_id}")
def grade_episode(episode_id: str, final_source: str, task_id: str):
    """
    Grade a completed episode.

    Parameters
    ----------
    episode_id   : the UUID returned in the observation after reset()
    final_source : name of the dataframe the agent submitted
    task_id      : t1 | t2 | t3  (needed to select the correct truth key)
    """
    truth_map = GLOBAL_TRUTH_STORE.get(episode_id)
    if not truth_map:
        raise HTTPException(
            status_code=404,
            detail=f"No truth snapshot found for episode_id='{episode_id}'. "
                   "Make sure to call reset() before grading."
        )

    # Pick the right truth key per task
    truth_key = {"t1": "web_forms", "t2": "merged_output", "t3": "merged_output"}.get(task_id)
    if truth_key is None:
        raise HTTPException(status_code=400, detail=f"Unknown task_id '{task_id}'")

    truth_df = truth_map.get(truth_key)
    if truth_df is None:
        raise HTTPException(status_code=500, detail=f"Truth key '{truth_key}' missing from snapshot.")

    # Get env instance safely
    env = GLOBAL_ENV_STORE.get(episode_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment instance not found")
        
    agent_df = env.final_df
    if agent_df is None:
        raise HTTPException(
            status_code=400, 
            detail="Agent has not submitted a final dataframe yet."
        )

    score = evaluate_dataframes(truth_df, agent_df)

    return {
        "episode_id": episode_id,
        "task_id": task_id,
        "score": score,
        "rows": len(agent_df)
    }

# ---------------------------------------------------------------------------
# /baseline  — DEMO ONLY, not part of core evaluation
# Lazy import keeps baseline.py failures from crashing the server on startup.
# ---------------------------------------------------------------------------
@router.get("/baseline")
def run_baseline():
    """
    DEMO ENDPOINT — runs the baseline inference script against all 3 tasks.
    Not required for OpenEnv evaluation. May add latency due to LLM calls.
    """
    try:
        from baseline import run_task   # lazy import — do not couple to server startup
        t1 = run_task("t1")
        t2 = run_task("t2")
        t3 = run_task("t3")
        return {"demo": True, "scores": {"t1": t1, "t2": t2, "t3": t3}}
    except ImportError:
        raise HTTPException(status_code=501, detail="baseline.py not available.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router)

def main():
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
