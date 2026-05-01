from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
import pandas as pd
from io import BytesIO

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

from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

import yaml
import server.environment as env_mod
print(f"DEBUG: env_mod path: {env_mod.__file__}")

from server.environment import CRMDataPipelineEnv, GLOBAL_TRUTH_STORE, GLOBAL_ENV_STORE
from server.graders import get_grader, evaluate_dataframes
from models import CRMPipelineAction, CRMPipelineObservation
from server.agent import plan_next_action, plan_full_pipeline
import os


app = create_fastapi_app(CRMDataPipelineEnv, CRMPipelineAction, CRMPipelineObservation)
router = APIRouter()

# Mount the beautiful UI we built in Phase 2
app.mount("/ui", StaticFiles(directory="public", html=True), name="ui")

@router.get("/")
def read_root():
    """Redirect root directly to the beautiful UI dashboard."""
    return RedirectResponse(url="/ui/index.html")

@router.post("/api/start_demo")
def start_demo():
    """Initializes the CRM environment natively and returns the messy raw data."""
    env = CRMDataPipelineEnv()
    os.environ["TASK_ID"] = "t1" # We use task 1 (Web Forms) for the main demo
    res = env.reset()
    episode_id = env.state.episode_id
    
    # Grab the messy data to show in the left UI pane
    raw_df = env.get_final_dataframe("donation_forms")
    # Convert to standard dictionary list for JS rendering, replace NaN with empty string
    raw_data = raw_df.fillna("").head(20).to_dict(orient="records")
    
    return {
        "episode_id": episode_id,
        "observation": res.observation.dict(),
        "raw_data": raw_data
    }

@router.post("/api/agent_step/{episode_id}")
def agent_step(episode_id: str):
    """Hits the local Gemma model to plan ONE action, then executes it.
    Passes already_done list so Gemma never repeats a (source, column) pair."""
    env = GLOBAL_ENV_STORE.get(episode_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment gone missing.")

    # Track which (source, column) combos have already been cleaned
    if not hasattr(env, "_already_done"):
        env._already_done = []

    # Get current observation (with actual historical reward)
    historical_reward = getattr(env, "_last_reward", 0.0)
    current_obs = env._build_observation(False, historical_reward).dict()
    # Inject the already-done list so Gemma skips finished columns
    current_obs["already_done"] = env._already_done

    # --- Let Gemma 4 decide the action ---
    gemma_action = plan_next_action(current_obs)

    # Record completed (source, column) pair to prevent repetition
    if gemma_action.source and gemma_action.column:
        done_entry = f"{gemma_action.source}.{gemma_action.column}"
        if done_entry not in env._already_done:
            env._already_done.append(done_entry)

    # Execute the action Gemma chose in the real environment
    result = env.step(gemma_action)

    # Fetch whichever table Gemma modified to show the user
    source_name = gemma_action.source or "donation_forms"
    if gemma_action.action_type.value == "SUBMIT_PIPELINE":
        source_name = gemma_action.final_source or "donation_forms"

    try:
        updated_df = env.get_final_dataframe(source_name)
        table_data = updated_df.fillna("").head(20).to_dict(orient="records")
    except:
        table_data = []

    return {
        "action": gemma_action.action_type.value,
        "reason": result.observation.last_action_feedback,
        "observation": result.observation.dict(),
        "table_data": table_data,
        "done": result.done
    }


@router.post("/api/run_full_pipeline/{episode_id}")
def run_full_pipeline(episode_id: str):
    """
    ⚡ FAST BATCH MODE — calls Gemma ONCE for the full plan, then executes
    every action locally without any further LLM round-trips.
    Returns the complete step-by-step log and the final cleaned table.
    """
    env = GLOBAL_ENV_STORE.get(episode_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment gone missing.")

    historical_reward = getattr(env, "_last_reward", 0.0)
    current_obs = env._build_observation(False, historical_reward).dict()

    # One Gemma call → full ordered action plan
    actions = plan_full_pipeline(current_obs)

    steps_log = []
    total_reward = 0.0
    final_done = False
    final_table_data = []

    for idx, action in enumerate(actions):
        result = env.step(action)
        total_reward += result.reward
        final_done = result.done

        source_name = action.source or ""
        if action.action_type.value == "SUBMIT_PIPELINE":
            source_name = action.final_source or source_name

        try:
            df = env.get_final_dataframe(source_name) if source_name else env.final_df
            if df is not None and not df.empty:
                final_table_data = df.fillna("").head(20).to_dict(orient="records")
        except Exception:
            pass

        step_entry = {
            "step": idx + 1,
            "action": action.action_type.value,
            "source": source_name,
            "column": action.column or "",
            "reward": round(result.reward, 4),
            "feedback": result.observation.last_action_feedback,
            "done": result.done,
        }
        steps_log.append(step_entry)
        print(f"   Step {idx+1}/{len(actions)}: {action.action_type.value} "
              f"[{source_name}.{action.column or '—'}] reward={result.reward:.3f}")

        if result.done:
            break

    return {
        "total_steps": len(steps_log),
        "total_reward": round(total_reward, 4),
        "done": final_done,
        "steps_log": steps_log,
        "table_data": final_table_data,
    }

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

@router.post("/api/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    """Receives user dataset and bootstraps Real Mode."""
    contents = await file.read()
    try:
        user_df = pd.read_csv(BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {e}")
        
    env = CRMDataPipelineEnv()
    res = env.reset_with_dataframe(user_df, source_name="user_upload")
    episode_id = env.state.episode_id
    
    raw_data = user_df.fillna("").head(20).to_dict(orient="records")
    
    return {
        "episode_id": episode_id,
        "observation": res.observation.dict(),
        "raw_data": raw_data
    }

@router.get("/api/download_csv/{episode_id}")
def download_csv(episode_id: str):
    """Exports the cleaned dataframe."""
    env = GLOBAL_ENV_STORE.get(episode_id)
    if not env or env.final_df is None:
        raise HTTPException(status_code=404, detail="No final cleaned data available.")
        
    csv_data = env.final_df.to_csv(index=False)
    return Response(
        content=csv_data, 
        media_type="text/csv", 
        headers={"Content-Disposition": f"attachment; filename=cleaned_ngo_data.csv"}
    )


app.include_router(router)

def main():
    """Entrypoint bound for Docker and local WSGI invocation."""
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
