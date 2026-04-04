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

@router.get("/")
def read_root():
    return {"status": "ok", "message": "CRM Pipeline Environment is running."}



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



app.include_router(router)

def main():
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
