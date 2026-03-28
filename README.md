# CRM Data Pipeline OpenEnv 📊

An environment that simulates the daily tasks of a real-world CRM Data Engineer. Instead of playing games, an AI agent must query, standardized, deduplicate, and merge messy real-world customer datasets into pristine warehouse tables. 

## The Task
Data sits in multiple silos (`web_forms`, `legacy_db`, `salesforce`) and has inconsistent lowercase rules, date formats, and duplicates. The Agent receives the target database schema and a set of available actions to mutate the Pandas DataFrames directly.

## Action Space
- `VIEW_SOURCE`
- `PROFILE_SOURCE`
- `STANDARDIZE_COLUMN` (Strategies: ISO_8601, LOWERCASE_STRIP, EXTRACT_NUMBERS, PHONE_E164)
- `HANDLE_MISSING` (FILL, DROP)
- `DEDUPLICATE`
- `MERGE_SOURCES`
- `SUBMIT_PIPELINE`

## Observation Space
- `current_task_objective`
- `schema_target`
- `available_sources`
- `current_view` (Markdown summary of dataset head)
- `last_action_feedback`
- `data_quality_report`

## Setup & Deployment
The environment natively complies with the [OpenEnv Specifications](https://huggingface.co/collections/openenv/environment-hub). 

### Local Execution
```bash
docker build -t crm-env .
docker run -p 8080:8080 crm-env
```

### Baseline Inference Test
Validates the local container and deterministic task grader by attempting all 3 tasks (Easy, Medium, Hard).
```bash
# Requires local server running
python inference.py
```

### Baseline Scores
Based on the default inference script baseline tests:
- **Task 1 (Easy):** 1.0 / 1.0
- **Task 2 (Medium):** 1.0 / 1.0
- **Task 3 (Hard):** 1.0 / 1.0
