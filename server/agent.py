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
You clean messy datasets autonomously. Look at the current state, and output valid JSON
representing your next chosen action. 

Current Observation:
{json.dumps(observation, indent=2)}

Output ONLY valid JSON matching this structure perfectly:
{{
    "action_type": "PROFILE_SOURCE",  // Must be one of the PipelineActionTypes
    "source": "example_table",
    "column": "email",
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
        # Fallback to keep the loop alive even if Gemma crashes
        return CRMPipelineAction(action_type="PROFILE_SOURCE", source="donation_forms")
