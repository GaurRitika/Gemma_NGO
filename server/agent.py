import requests
import json
from models import CRMPipelineAction

OLLAMA_API_URL = "http://localhost:11434/api/generate"
GEMMA_MODEL_NAME = "gemma" # Default tag for Gemma in Ollama

def plan_next_action(observation: dict) -> CRMPipelineAction:
    """
    Connects to the local Ollama instance running Gemma 4.
    Passes the current data state (observation) and forces a strict JSON return
    that maps perfectly to the CRMPipelineAction Pydantic model.
    """
    
    prompt = f"""You are the Gemma 4 CRM Data Engineer Copilot.
You are operating inside an RL Environment. You must clean messy datasets autonomously. Look at the current observation state, and output valid JSON representing your next chosen action. 

AVAILABLE ACTION TYPES:
- "STANDARDIZE_COLUMN": Clean and format string columns (Strategies: "LOWERCASE_STRIP", "EXTRACT_NUMBERS", "TO_DATETIME_ISO")
- "HANDLE_MISSING": Fix missing/null values (Strategies: "FILL_MEAN", "FILL_MODE", "DROP_ROW", "FILL_VALUE")
- "DEDUPLICATE": Remove identical human duplicate rows (Strategies: "FUZZY_NAME_PHONE", "EXACT_EMAIL")
- "PROFILE_SOURCE": Analyze a source dataset (Use this sparingly, usually once at the start).
- "SUBMIT_PIPELINE": Call this ONLY when the data is fully clean and you are ready to terminate the episode.

INSTRUCTIONS:
1. Read the "observation" JSON carefully. If you receive a Penalty or Negative Reward, YOU MUST CHANGE YOUR STRATEGY or PICK A DIFFERENT COLUMN. Do NOT repeat the exact same action!
2. Do NOT just copy the example JSON. Look at the null counts and dirty formats in the current observation and clean the dirtiest columns first!
3. Output ONLY raw JSON matching this structure perfectly. When no columns have missing values, duplicates, or formatting issues, select "SUBMIT_PIPELINE".

Current Observation:
{json.dumps(observation, indent=2)}

Example JSON Output format:
{{
    "action_type": "STANDARDIZE_COLUMN", 
    "source": "user_upload",
    "column": "<identify_dirty_column_from_obs>",
    "standardization_strategy": "LOWERCASE_STRIP"
}}
"""

    try:
        print(f"🧠 Asking Gemma 4 to reason about the current observation...")
        resp = requests.post(OLLAMA_API_URL, json={
            "model": GEMMA_MODEL_NAME,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0} # Predictable deterministic outputs
        })
        resp.raise_for_status()
        
        raw_json = resp.json().get("response", "{}")
        print(f"✅ Gemma 4 Action Payload: {raw_json}")
        
        action_dict = json.loads(raw_json)
        
        # Validates and converts to OpenEnv Pydantic action!
        return CRMPipelineAction(**action_dict)
        
    except Exception as e:
        print(f"⚠️ Gemma Agent Error: {e}. Is Ollama running?")
        raise RuntimeError(f"Gemma API failure or formatting error: {e}")
