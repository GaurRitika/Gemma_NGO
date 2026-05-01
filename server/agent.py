# -*- coding: utf-8 -*-
import sys
import io
import requests
import json
import time
from models import CRMPipelineAction

# Force UTF-8 output so emoji in logs don't crash on Windows cp1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

OLLAMA_API_URL  = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"   # fast health probe
GEMMA_MODEL_NAME = "gemma"  # Default tag for Gemma in Ollama

# How long to wait for Ollama before giving up and using rule-based planner
OLLAMA_TIMEOUT_SEC = 8


def _check_ollama_alive() -> bool:
    """Probe Ollama with a 2-second timeout. Returns False if unreachable/slow."""
    try:
        r = requests.get(OLLAMA_TAGS_URL, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


# Maps any variant field names Gemma might hallucinate -> correct Pydantic field name
_FIELD_ALIASES = {
    "handle_missing_strategy": "missing_strategy",
    "missing_value_strategy":  "missing_strategy",
    "fill_value":              "fallback_value",
    "fallback":                "fallback_value",
    "dedup_strategy":          "deduplication_strategy",
    "std_strategy":            "standardization_strategy",
}

# Only these keys are valid on CRMPipelineAction — anything else is dropped silently
_VALID_KEYS = {
    "action_type", "source", "source2", "column",
    "standardization_strategy", "missing_strategy",
    "deduplication_strategy", "fallback_value",
    "join_key", "conflict_rule", "final_source",
    "query", "output_table",
}


def _normalize(action_dict: dict) -> dict:
    """Remap any variant key names Gemma produces into the exact Pydantic field names,
    then strip any remaining unknown keys so Pydantic never raises extra-field errors."""
    normalized = {_FIELD_ALIASES.get(k, k): v for k, v in action_dict.items()}
    return {k: v for k, v in normalized.items() if k in _VALID_KEYS}


def _infer_strategy(col: str, dtype: str) -> dict:
    """
    Deterministically infer the right cleaning strategy from column name + dtype.
    Returns a partial action dict (without action_type / source).
    """
    col_lower = col.lower()
    if any(k in col_lower for k in ["email", "e-mail", "mail", "contact_email"]):
        return {"standardization_strategy": "LOWERCASE_STRIP"}
    if any(k in col_lower for k in ["phone", "mobile", "tel", "home_phone", "contact_number"]):
        return {"standardization_strategy": "EXTRACT_NUMBERS"}
    if any(k in col_lower for k in ["date", "time", "created", "updated", "signup", "registration"]):
        return {"standardization_strategy": "TO_DATETIME_ISO"}
    if any(k in col_lower for k in ["name", "donor", "volunteer", "contact", "person", "first", "last"]):
        return {"standardization_strategy": "LOWERCASE_STRIP"}
    if "int" in dtype or "float" in dtype:
        return {"standardization_strategy": "EXTRACT_NUMBERS"}
    # Default: text clean
    return {"standardization_strategy": "LOWERCASE_STRIP"}


# ─────────────────────────────────────────────────────────────────────────────
# FULL BATCH PLANNER — asks Gemma ONCE for the ENTIRE cleaning plan
# ─────────────────────────────────────────────────────────────────────────────

def plan_full_pipeline(observation: dict) -> list:
    """
    Calls Gemma ONCE asking for a complete, ordered JSON array of ALL actions
    needed to clean every source table end-to-end.  Falls back to a deterministic
    rule-based plan if Gemma returns anything unparseable or times out.

    Returns: list[CRMPipelineAction]  (ready to execute in order)
    """
    sources        = observation.get("available_sources", [])
    quality_report = observation.get("data_quality_report", "")
    schema_target  = observation.get("schema_target", {})

    prompt = f"""You are the Gemma 4 CRM Data Engineer Copilot.

Your job is to produce a COMPLETE, ORDERED JSON array of cleaning actions to fully clean ALL source tables.
Output ONLY a raw JSON array - no markdown, no explanation, no extra text.

AVAILABLE SOURCES: {json.dumps(sources)}
DATA QUALITY REPORT:
{quality_report}
SCHEMA TARGET: {json.dumps(schema_target)}

ACTION TYPES (use exactly these field names):
1. STANDARDIZE_COLUMN  -> {{"action_type":"STANDARDIZE_COLUMN","source":"<src>","column":"<col>","standardization_strategy":"LOWERCASE_STRIP|EXTRACT_NUMBERS|TO_DATETIME_ISO"}}
2. HANDLE_MISSING      -> {{"action_type":"HANDLE_MISSING","source":"<src>","column":"<col>","missing_strategy":"FILL_VALUE|DROP_ROW","fallback_value":"N/A"}}
3. DEDUPLICATE         -> {{"action_type":"DEDUPLICATE","source":"<src>","deduplication_strategy":"EXACT_EMAIL|FUZZY_NAME_PHONE"}}
4. SUBMIT_PIPELINE     -> {{"action_type":"SUBMIT_PIPELINE","final_source":"<src>"}}  <- MUST be the LAST item

STRATEGY RULES:
- email / contact_email / mail -> LOWERCASE_STRIP
- phone / mobile / home_phone  -> EXTRACT_NUMBERS
- date / signup / time         -> TO_DATETIME_ISO
- name / donor / person / text -> LOWERCASE_STRIP

RULES:
- Process EVERY source table listed in AVAILABLE SOURCES.
- For each source: first STANDARDIZE all dirty columns, then HANDLE_MISSING nulls, then DEDUPLICATE.
- Do NOT repeat the same (source, column) pair.
- End with exactly ONE SUBMIT_PIPELINE using the primary/first source or merged output.
- Output ONLY the JSON array, nothing else.

Example output format:
[
  {{"action_type":"STANDARDIZE_COLUMN","source":"donation_forms","column":"email","standardization_strategy":"LOWERCASE_STRIP"}},
  {{"action_type":"HANDLE_MISSING","source":"donation_forms","column":"phone","missing_strategy":"FILL_VALUE","fallback_value":""}},
  {{"action_type":"DEDUPLICATE","source":"donation_forms","deduplication_strategy":"EXACT_EMAIL"}},
  {{"action_type":"SUBMIT_PIPELINE","final_source":"donation_forms"}}
]
"""

    # Fast alive-check - skip Gemma call entirely if Ollama won't respond
    if not _check_ollama_alive():
        print("[Batch Planner] Ollama unreachable - using rule-based planner instantly.")
        return _rule_based_plan(observation)

    t0 = time.time()
    try:
        print(f"[Batch Planner] Asking Gemma 4 for FULL pipeline plan ({len(sources)} sources)...")
        resp = requests.post(OLLAMA_API_URL, json={
            "model": GEMMA_MODEL_NAME,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 2048},
        }, timeout=OLLAMA_TIMEOUT_SEC)
        resp.raise_for_status()

        raw = resp.json().get("response", "[]")
        print(f"[Batch Planner] Gemma responded in {time.time()-t0:.1f}s")
        print(f"   Raw payload: {raw[:300]}...")

        # Gemma sometimes wraps the array in {"actions": [...]} - unwrap it
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            for key in ("actions", "plan", "steps", "pipeline"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                # Might be a single action dict - wrap in list
                parsed = [parsed]

        if not isinstance(parsed, list) or len(parsed) == 0:
            raise ValueError("Gemma returned empty or non-list response")

        actions = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            item = _normalize(item)
            try:
                actions.append(CRMPipelineAction(**item))
            except Exception as parse_err:
                print(f"   [WARN] Skipping malformed action {item}: {parse_err}")

        if not actions:
            raise ValueError("No valid actions parsed from Gemma response")

        print(f"[Batch Planner] Parsed {len(actions)} actions from Gemma plan.")
        return actions

    except Exception as e:
        print(f"[Batch Planner] Gemma failed ({e}). Falling back to rule-based planner.")
        return _rule_based_plan(observation)


def _rule_based_plan(observation: dict) -> list:
    """
    Deterministic fallback: scan every source table from the quality report
    and produce a complete action list WITHOUT calling Gemma.
    Runs in <1ms -- always succeeds.
    """
    import re

    sources        = observation.get("available_sources", [])
    quality_report = observation.get("data_quality_report", "")

    # Parse the quality report per-source block
    # Format: "### Source: <name> (<N> rows)\n- **col**: type=..., nulls=N"
    actions = []
    primary_source = sources[0] if sources else "donation_forms"

    # Build per-source column map from the quality report
    source_cols: dict = {}  # source_name -> list of (col, dtype, null_count)
    current_src = None
    col_re = re.compile(r"\*\*(.+?)\*\*.*?type=(\S+).*?nulls=(\d+)")
    src_re = re.compile(r"### Source:\s*(\S+)")

    for line in quality_report.splitlines():
        src_match = src_re.search(line)
        if src_match:
            current_src = src_match.group(1)
            source_cols.setdefault(current_src, [])
            continue
        col_match = col_re.search(line)
        if col_match and current_src:
            col, dtype, nulls = col_match.groups()
            source_cols[current_src].append((col, dtype, int(nulls)))

    # If report has no source headers, assume all cols belong to primary source
    if not source_cols and col_re.search(quality_report):
        col_specs = col_re.findall(quality_report)
        source_cols[primary_source] = [(c, d, int(n)) for c, d, n in col_specs]

    # Fallback: use available_sources if report parsing found nothing
    if not source_cols:
        for src in sources:
            source_cols[src] = []

    # Generate actions per source
    for source in sources:
        cols = source_cols.get(source, [])
        has_email = False

        for col, dtype, null_count in cols:
            strat = _infer_strategy(col, dtype)["standardization_strategy"]

            # STANDARDIZE always
            actions.append(CRMPipelineAction(
                action_type="STANDARDIZE_COLUMN",
                source=source,
                column=col,
                standardization_strategy=strat
            ))

            # HANDLE MISSING only when report shows actual nulls (null_count > 0)
            # This avoids -0.1 penalties for calling HANDLE_MISSING on clean columns
            if null_count > 0:
                fill = "" if strat in ("TO_DATETIME_ISO", "EXTRACT_NUMBERS") else "N/A"
                actions.append(CRMPipelineAction(
                    action_type="HANDLE_MISSING",
                    source=source,
                    column=col,
                    missing_strategy="FILL_VALUE",
                    fallback_value=fill
                ))

            if "email" in col.lower() or "mail" in col.lower():
                has_email = True

        # DEDUPLICATE per source if email col exists
        if has_email:
            actions.append(CRMPipelineAction(
                action_type="DEDUPLICATE",
                source=source,
                deduplication_strategy="EXACT_EMAIL"
            ))

    actions.append(CRMPipelineAction(
        action_type="SUBMIT_PIPELINE",
        final_source=primary_source
    ))

    print(f"[Rule-Based Planner] Generated {len(actions)} actions for {len(sources)} source(s).")
    return actions


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-STEP PLANNER — kept for backwards-compat with /api/agent_step
# ─────────────────────────────────────────────────────────────────────────────

def plan_next_action(observation: dict) -> CRMPipelineAction:
    """
    Single-step planning: calls Gemma for ONE action.
    Now also passes `already_done` so Gemma never repeats a column.
    Falls back to rule-based planner if Ollama is unavailable/slow.
    """
    already_done = observation.get("already_done", [])
    already_done_str = json.dumps(already_done) if already_done else "[]"

    prompt = f"""You are the Gemma 4 CRM Data Engineer Copilot.
You are operating inside an RL Environment. You must clean messy datasets autonomously.
Look at the current observation state and output ONE valid JSON action.

AVAILABLE ACTION TYPES:

1. STANDARDIZE_COLUMN:
   {{"action_type": "STANDARDIZE_COLUMN", "source": "<source>", "column": "<col>", "standardization_strategy": "LOWERCASE_STRIP|EXTRACT_NUMBERS|TO_DATETIME_ISO"}}

2. HANDLE_MISSING:
   {{"action_type": "HANDLE_MISSING", "source": "<source>", "column": "<col>", "missing_strategy": "FILL_VALUE|DROP_ROW", "fallback_value": "N/A"}}

3. DEDUPLICATE:
   {{"action_type": "DEDUPLICATE", "source": "<source>", "deduplication_strategy": "EXACT_EMAIL|FUZZY_NAME_PHONE"}}

4. SUBMIT_PIPELINE:
   {{"action_type": "SUBMIT_PIPELINE", "final_source": "<source>"}}

STRATEGY RULES:
  - email / contact_email columns -> LOWERCASE_STRIP
  - phone / mobile / home_phone   -> EXTRACT_NUMBERS
  - date / time columns           -> TO_DATETIME_ISO
  - name / text columns           -> LOWERCASE_STRIP

ALREADY COMPLETED - DO NOT REPEAT THESE:
{already_done_str}

Current Observation:
{json.dumps(observation, indent=2)}
"""

    # Fast alive-check before blocking on a slow Ollama call
    if not _check_ollama_alive():
        print("[Step Planner] Ollama unreachable - using rule-based single-step fallback.")
        fallback_actions = _rule_based_plan(observation)
        return fallback_actions[0] if fallback_actions else CRMPipelineAction(
            action_type="SUBMIT_PIPELINE",
            final_source=(observation.get("available_sources") or ["donation_forms"])[0]
        )

    try:
        print("[Step Planner] Asking Gemma 4 to reason about the current observation...")
        resp = requests.post(OLLAMA_API_URL, json={
            "model": GEMMA_MODEL_NAME,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0},
        }, timeout=OLLAMA_TIMEOUT_SEC)
        resp.raise_for_status()

        raw_json = resp.json().get("response", "{}")
        print(f"[Step Planner] Gemma action: {raw_json}")

        action_dict = json.loads(raw_json)
        action_dict = _normalize(action_dict)
        return CRMPipelineAction(**action_dict)

    except Exception as e:
        print(f"[Step Planner] Gemma error: {e} - falling back to rule-based single step.")
        fallback_actions = _rule_based_plan(observation)
        already_done_set = set(observation.get("already_done", []))
        for action in fallback_actions:
            key = f"{action.source}.{action.column}" if action.column else action.action_type
            if key not in already_done_set:
                return action
        return CRMPipelineAction(
            action_type="SUBMIT_PIPELINE",
            final_source=(observation.get("available_sources") or ["donation_forms"])[0]
        )
