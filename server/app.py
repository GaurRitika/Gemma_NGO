from fastapi import APIRouter
import json

try:
    from openenv.core.env_server import create_fastapi_app
except ImportError:
    from fastapi import FastAPI
    def create_fastapi_app(env_cls, act_cls=None, obs_cls=None): return FastAPI()

from server.environment import CRMDataPipelineEnv
from server.graders import get_grader
from models import CRMPipelineAction, CRMPipelineObservation

app = create_fastapi_app(CRMDataPipelineEnv, CRMPipelineAction, CRMPipelineObservation)
router = APIRouter()

import yaml
from baseline import run_task

@router.get("/tasks")
def list_tasks():
    with open("openenv.yaml", "r") as f:
        # Dynamically parsing the true config instead of hardcoding
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

@router.get("/baseline")
def run_baseline():
    try:
        # Running the python function directly instead of risky subprocess calls
        t1 = run_task("t1")
        t2 = run_task("t2")
        t3 = run_task("t3")
        return {
            "scores": {"t1": t1, "t2": t2, "t3": t3}
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/set_task/{task_id}")
def set_task(task_id: str):
    import os
    os.environ["CURRENT_TASK_ID"] = task_id
    return {"status": "ok"}

@router.post("/grader/{task_id}")
def grade_episode(task_id: str):
    from server.environment import LAST_ENV_INSTANCE
    from server.graders import get_grader
    
    env_instance = LAST_ENV_INSTANCE.get(task_id)
    if not env_instance:
        return {"score": 0.0, "error": "Environment instance for this task_id not found on server."}
        
    grader_func = get_grader(task_id)
    if grader_func:
        score = grader_func(env_instance)
        return {"score": score}
        
    return {"score": 0.0, "error": "Grader not found"}

app.include_router(router)
