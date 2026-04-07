"""
Baseline Inference Script for CRM Data Pipeline OpenEnv Environment.

Requires HF_TOKEN, API_BASE_URL, and MODEL_NAME environment variables to be set before running.

DO NOT hardcode API keys in this file.
"""
import os
import json
import time
import requests
from typing import List, Optional
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError
from client import CRMDataPipelineEnvClient
from models import CRMPipelineAction, PipelineActionType

# Load .env file automatically if present (safe — doesn't override existing env vars)
load_dotenv()

# ============================================================
# SECURITY: API key is ONLY read from environment variables.
# If missing, we raise immediately rather than silently failing.
# ============================================================
API_BASE_URL = os.environ["API_BASE_URL"]
MODEL_NAME = os.getenv("MODEL_NAME", "<your-active-model-name>")
API_KEY = os.environ["API_KEY"]
# Optional - if you use from_docker_image():
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

openai_client = OpenAI(
    api_key=API_KEY,
    base_url=API_BASE_URL
)
MAX_STEPS_PER_TASK = 15  # Up from 6 — enough for complex T3 multi-merge pipelines

SYSTEM_PROMPT = """You are an expert CRM Data Engineer operating a data pipeline.
Your goal is to clean, deduplicate, standardize, and merge messy customer datasets.

You will be given the current state of the pipeline (objective, available sources, schema targets, and feedback from your last action).
Based on this, respond with EXACTLY one JSON action object — no other text.

Valid action_types and their required fields:
- VIEW_SOURCE: {"action_type": "VIEW_SOURCE", "source": "<name>"}
- PROFILE_SOURCE: {"action_type": "PROFILE_SOURCE", "source": "<name>"}
- STANDARDIZE_COLUMN: {"action_type": "STANDARDIZE_COLUMN", "source": "<name>", "column": "<col>", "standardization_strategy": "LOWERCASE_STRIP|EXTRACT_NUMBERS|TO_DATETIME_ISO"}
- HANDLE_MISSING: {"action_type": "HANDLE_MISSING", "source": "<name>", "column": "<col>", "missing_strategy": "DROP_ROW|FILL_VALUE", "fallback_value": "<val or null>"}
- DEDUPLICATE: {"action_type": "DEDUPLICATE", "source": "<name>", "deduplication_strategy": "EXACT_EMAIL|FUZZY_NAME_PHONE"}
- EXECUTE_SQL: {"action_type": "EXECUTE_SQL", "query": "<SQL>", "output_table": "<name>"}
- SUBMIT_PIPELINE: {"action_type": "SUBMIT_PIPELINE", "final_source": "<name>"}

Rules:
1. Always VIEW_SOURCE or PROFILE_SOURCE a new source before standardizing it.
2. SUBMIT_PIPELINE is final — only submit when the data is fully cleaned.
3. For multi-source tasks (T2, T3) use EXECUTE_SQL to JOIN or UNION sources.
4. Remove bot/outlier rows using EXECUTE_SQL with WHERE filters on customer_id or email.
"""

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


def build_user_prompt(obs, steps_remaining: int, task_id: str) -> str:
    return f"""
=== CRM Pipeline Agent ===
Task ID: {task_id} | Steps Remaining: {steps_remaining}
Objective: {obs.current_task_objective}

Available Sources: {obs.available_sources}
Target Schema: {json.dumps(obs.schema_target, indent=2)}

Current View (last 3 rows):
{obs.current_view}

Data Quality Report:
{obs.data_quality_report or "Not profiled yet."}

Last Action Feedback:
{obs.last_action_feedback or "None"}

Decide your next action (one JSON object only):
"""

def call_gpt_with_retry(prompt: str, max_retries: int = 3) -> dict | None:
    """Call GPT with retry logic for rate limits and transient API errors."""
    for attempt in range(max_retries):
        try:
            resp = openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Low temperature for more deterministic responses
            )
            raw = resp.choices[0].message.content
            return json.loads(raw)
        except RateLimitError:
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            print(f"[DEBUG] [GPT] Rate limit hit. Retrying in {wait_time}s...", flush=True)
            time.sleep(wait_time)
        except APIError as e:
            print(f"[DEBUG] [GPT] API Error on attempt {attempt + 1}: {e}", flush=True)
            time.sleep(1)
        except json.JSONDecodeError as e:
            print(f"[DEBUG] [GPT] JSON decode failed: {e}", flush=True)
            return None
    return None

def build_smart_fallback(obs, step: int, task_id: str) -> dict:
    """A smarter fallback plan the baseline runs if GPT completely fails."""
    sources = obs.available_sources or ["web_forms"]
    target = sources[0]

    fallback_pipeline = {
        "t1": [
            {"action_type": "PROFILE_SOURCE", "source": "web_forms"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_forms", "column": "email", "standardization_strategy": "LOWERCASE_STRIP"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_forms", "column": "name", "standardization_strategy": "LOWERCASE_STRIP"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_forms", "column": "phone", "standardization_strategy": "EXTRACT_NUMBERS"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_forms", "column": "signup_date", "standardization_strategy": "TO_DATETIME_ISO"},
            {"action_type": "DEDUPLICATE", "source": "web_forms", "deduplication_strategy": "EXACT_EMAIL"},
            {"action_type": "EXECUTE_SQL", "query": "SELECT * FROM web_forms WHERE customer_id != '???' AND email NOT LIKE '%bot%'", "output_table": "web_forms_clean"},
            {"action_type": "SUBMIT_PIPELINE", "final_source": "web_forms_clean"},
        ],
        "t2": [
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_forms", "column": "email", "standardization_strategy": "LOWERCASE_STRIP"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_forms", "column": "name", "standardization_strategy": "LOWERCASE_STRIP"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_forms", "column": "phone", "standardization_strategy": "EXTRACT_NUMBERS"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_forms", "column": "signup_date", "standardization_strategy": "TO_DATETIME_ISO"},
            {"action_type": "EXECUTE_SQL", "query": "SELECT * FROM web_forms WHERE customer_id != '???' AND email NOT LIKE '%bot%'", "output_table": "web_forms_clean"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "legacy_db", "column": "email", "standardization_strategy": "LOWERCASE_STRIP"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "legacy_db", "column": "name", "standardization_strategy": "LOWERCASE_STRIP"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "legacy_db", "column": "phone", "standardization_strategy": "EXTRACT_NUMBERS"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "legacy_db", "column": "signup_date", "standardization_strategy": "TO_DATETIME_ISO"},
            {"action_type": "EXECUTE_SQL", "query": "SELECT * FROM legacy_db WHERE customer_id != '???' AND email NOT LIKE '%bot%'", "output_table": "legacy_db_clean"},
            {"action_type": "EXECUTE_SQL", "query": "SELECT * FROM web_forms_clean UNION ALL SELECT * FROM legacy_db_clean", "output_table": "merged_output"},
            {"action_type": "DEDUPLICATE", "source": "merged_output", "deduplication_strategy": "EXACT_EMAIL"},
            {"action_type": "SUBMIT_PIPELINE", "final_source": "merged_output"},
        ],
        "t3": [
            {"action_type": "STANDARDIZE_COLUMN", "source": "salesforce", "column": "email", "standardization_strategy": "LOWERCASE_STRIP"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "salesforce", "column": "phone", "standardization_strategy": "EXTRACT_NUMBERS"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_leads", "column": "email", "standardization_strategy": "LOWERCASE_STRIP"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "web_leads", "column": "phone", "standardization_strategy": "EXTRACT_NUMBERS"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "legacy_db", "column": "contact_email", "standardization_strategy": "LOWERCASE_STRIP"},
            {"action_type": "STANDARDIZE_COLUMN", "source": "legacy_db", "column": "home_phone", "standardization_strategy": "EXTRACT_NUMBERS"},
            {"action_type": "EXECUTE_SQL", "query": "SELECT MAX(customer_id) as customer_id, email, MAX(phone) as phone FROM (SELECT customer_id, email, phone FROM salesforce WHERE customer_id != '???' AND email NOT LIKE '%bot%' UNION ALL SELECT customer_id, email, phone FROM web_leads WHERE customer_id IS NOT NULL AND email NOT LIKE '%bot%' UNION ALL SELECT REPLACE(legacy_id, 'OLD-', 'CUST_') AS customer_id, contact_email AS email, home_phone AS phone FROM legacy_db WHERE legacy_id != '???' AND contact_email NOT LIKE '%bot%') GROUP BY email", "output_table": "merged_output"},
            {"action_type": "SUBMIT_PIPELINE", "final_source": "merged_output"},
        ],
    }

    plan = fallback_pipeline.get(task_id, [])
    if step < len(plan):
        return plan[step]
    # Final fallback: just submit whatever is available
    return {"action_type": "SUBMIT_PIPELINE", "final_source": target}

def validate_action(payload: dict) -> CRMPipelineAction | None:
    """Validate GPT action payload. Return None if invalid to use fallback."""
    try:
        action_type_val = payload.get("action_type", "")
        if not action_type_val or action_type_val not in [e.value for e in PipelineActionType]:
            print(f"[DEBUG] [WARN] Invalid action_type: {action_type_val!r}", flush=True)
            return None
        return CRMPipelineAction(**payload)
    except Exception as e:
        print(f"[DEBUG] [WARN] Action validation failed: {e}", flush=True)
        return None


class RuleBasedBaseline:
    """A non-LLM baseline that follows a hardcoded cleaning script."""
    def __init__(self, task_id: str):
        self.task_id = task_id

    def act(self, obs, step: int) -> dict:
        return build_smart_fallback(obs, step, self.task_id)

def run_task(task_id: str, use_llm: bool = True) -> float:
    base_url = os.environ.get("OPENENV_BASE_URL", "http://127.0.0.1:8080")
    
    score = 0.0
    rewards = []
    
    log_start(task=task_id, env="crm_data_pipeline", model=MODEL_NAME)

    try:
        with CRMDataPipelineEnvClient(base_url=base_url).sync() as env:
            os.environ["TASK_ID"] = task_id
            result = env.reset()
            done = False
            steps = 0
            
            episode_id = None
            if getattr(env, "state", None) and getattr(env.state, "episode_id", None):
                episode_id = env.state.episode_id
            
            if not episode_id and result and result.observation:
                import re
                feedback = getattr(result.observation, "last_action_feedback", "")
                m = re.search(r"Episode: ([\w-]+)", feedback)
                if m:
                    episode_id = m.group(1)

            agent = RuleBasedBaseline(task_id)
            action = None

            while not done and steps < MAX_STEPS_PER_TASK:
                steps += 1
                obs = result.observation
                steps_remaining = MAX_STEPS_PER_TASK - steps
                
                payload = None
                if use_llm:
                    prompt = build_user_prompt(obs, steps_remaining, task_id)
                    payload = call_gpt_with_retry(prompt)

                action = validate_action(payload) if payload else None

                if action is None:
                    if use_llm:
                        print(f"[DEBUG] [FALLBACK] Step {steps}: using smart fallback pipeline", flush=True)
                    payload = agent.act(obs, steps - 1)
                    action = validate_action(payload)

                if action is None:
                    break

                # Prepare action string for logging
                if isinstance(action, CRMPipelineAction):
                    action_dict = {
                        k: v for k, v in action.__dict__.items() if v is not None
                    }
                    action_str = json.dumps(action_dict).replace("\n", "").replace("\r", "")
                else:
                    action_str = "unknown"

                result = env.step(action)
                done = result.done
                
                # We record the reward for this step
                reward = result.reward if result.reward is not None else 0.0
                rewards.append(reward)
                
                # Check for errors
                error_msg = getattr(result.observation, "last_action_feedback", None)
                if error_msg and error_msg.startswith("Error:"):
                    error = error_msg
                else:
                    error = None
                    
                log_step(step=steps, action=action_str, reward=reward, done=done, error=error)

            score = result.reward if result and result.done else 0.0
            score = float(score) if score else 0.0

            print(f"[DEBUG] Final Score [{task_id}]: {score:.4f}", flush=True)

    except Exception as e:
        if "1000 (OK)" not in str(e):
            print(f"[DEBUG] Runtime Exception in task {task_id}: {e}", flush=True)
        else:
            print(f"[DEBUG] Connection cleanly closed.", flush=True)

    # Determine success threshold (we can assume score > 0 means some success)
    success = score > 0.5
    log_end(success=success, steps=steps, score=score, rewards=rewards)
    
    return score

if __name__ == "__main__":
    results = {}
    for task_id in ["t1", "t2", "t3"]:
        results[task_id] = run_task(task_id, use_llm=True)

    results["average"] = sum(results.values()) / 3
    print("[DEBUG] === Final Scores ===", flush=True)
    print("[DEBUG] " + json.dumps(results).replace("\n", ""), flush=True)
