from fastapi import APIRouter, HTTPException

"""
Server bootstrap for the CRM Data Pipeline OpenEnv Environment.
Provides REST APIs for standard OpenEnv protocol (/step, /reset, /state) 
as well as a custom /grader endpoint specifically built for end-of-episode evaluation.
"""

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
    """Health check endpoint to ensure server runtime stability."""
    return {"status": "ok", "message": "CRM Pipeline Environment is actively running."}


@router.post("/grader/{episode_id}")
def grade_episode(episode_id: str, final_source: str, task_id: str):
    """
    Grades a completed episodic run by comparing the agent's final state 
    against the pristine Ground Truth snapshot securely cached during initialization.

    Parameters
    ----------
    episode_id   : Unique UUID isolating the agent's session memory.
    final_source : The DataFrame pointer representing the agent's submitted work.
    task_id      : Difficulty identifier ('t1', 't2', 't3') used to fetch correct truth schema.
    """
    
    truth_map = GLOBAL_TRUTH_STORE.get(episode_id)
    
    if not truth_map:
        raise HTTPException(
            status_code=404,
            detail=f"No underlying truth snapshot found for episode_id='{episode_id}'. "
                   "Ensure /reset is called explicitly before invoking the grader engine."
        )

    # Establish correct truth reference mapping based on task complexity
    truth_key = {"t1": "web_forms", "t2": "merged_output", "t3": "merged_output"}.get(task_id)
    if truth_key is None:
        raise HTTPException(status_code=400, detail=f"Unrecognized task_id constraint '{task_id}'.")

    truth_df = truth_map.get(truth_key)
    if truth_df is None:
        raise HTTPException(status_code=500, detail=f"Target truth key '{truth_key}' is missing from the state snapshot.")

    env = GLOBAL_ENV_STORE.get(episode_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment instance allocation not found in active memory.")
        
    agent_df = env.final_df
    if agent_df is None:
        raise HTTPException(
            status_code=400, 
            detail="The active agent has not materialized a final dataframe for submission."
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
    """Entrypoint bound for Docker and local WSGI invocation."""
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
