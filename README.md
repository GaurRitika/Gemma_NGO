---
title: CRM Data Pipeline
emoji: ⚙️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8080
pinned: false
---

# ⚙️ CRM Data Pipeline Environment

> **A Real-World Autonomous Data Engineering Benchmark**

[![OpenEnv Compliant](https://img.shields.io/badge/OpenEnv-Compliant-brightgreen.svg)](#) [![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue.svg)](#) [![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](#)

---

## 📖 1. Overview & Motivation

The **CRM Data Pipeline Environment** is a production-grade testbed designed to evaluate the operational reasoning, planning, and code-generation capabilities of autonomous AI agents. Unlike standard game or toy environments, this simulates a high-impact, real-world data engineering workload: **cleaning, standardizing, and unifying messy customer datasets**.

In enterprise environments, CRM data suffers from formatting inconsistencies, null values, unstructured inputs, and duplicates. Autonomous agents must systematically profile sources (Salesforce, Web Leads, Legacy Databases), apply normalization strategies, execute complex SQL joins, and synthesize a pristine, analytics-ready master table.

This environment is built strictly upon the **OpenEnv Specification**, providing a formalized interface for researchers to evaluate frontier LLMs executing multi-step data transformations.

---

## 🏗️ 2. Environment Architecture

This environment models a **Partially Observable Markov Decision Process (POMDP)**. The agent cannot see the full ground truth but must infer the state of the data by profiling and sampling the data actively.

```mermaid
graph TD
    classDef agent fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff,rx:4px,ry:4px;
    classDef sys fill:#0f172a,stroke:#64748b,stroke-width:2px,color:#fff,rx:4px,ry:4px;
    classDef output fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff,rx:4px,ry:4px;
    
    A[LLM Agent]:::agent -- 1. Step(Action) --> B(FastAPI Server):::sys
    B -- 2. Mutate Memory --> C[(Pandas DataFrame)]:::sys
    C -- 3. Assess Progress --> D[Reward Function]:::sys
    D -- 4. Return Observation --> A
    
    A -- 5. SUBMIT_PIPELINE --> F[Grader Engine]:::sys
    E[(Ground Truth)]:::sys -. 6. Compare .-> F
    F -- 7. Final Score --> G[Result (0.0 - 1.0)]:::output
```

### 🎯 Reward Signal
To conquer the sparse-reward problem typical in code generation, this environment implements a **Dense Heuristic Reward**:
- **Progressive Rewards ($+0.03 \to +0.05$)**: Awarded immediately for successful data normalization or deduplication steps.
- **Destructive Penalties ($-0.1 \to -0.5$)**: Deducted for erratic actions like SQL syntax errors or attempting premature submission.
- **Terminal Accuracy Score ($0.0 \to 1.0$)**: Scored dynamically by the Grader Engine using stringency row/column matching against a hidden Ground Truth.

---

## 🕹️ 3. Action Space

Agents define their operations using a strictly-typed JSON payload serialized to the `CRMPipelineAction` Pydantic model. 

| Action Type | Description | Required Arguments |
| :--- | :--- | :--- |
| `VIEW_SOURCE` | Retrieve standard markdown table previews of a source. | `source` |
| `PROFILE_SOURCE` | Generate a statistical quality report (nulls, types). | `source` |
| `STANDARDIZE_COLUMN` | Apply deterministic transformations to a column. | `source`, `column`, `standardization_strategy` |
| `HANDLE_MISSING` | Resolve missing values. | `source`, `column`, `missing_strategy` |
| `DEDUPLICATE` | Strip duplicate values logically. | `source`, `deduplication_strategy` |
| `EXECUTE_SQL` | Perform advanced inner-joins or custom filters. | `query`, `output_table` |
| `SUBMIT_PIPELINE` | Conclude the episode and trigger the final grader evaluation. | `final_source` |

> [!TIP]
> **Safety Guardrails:** `EXECUTE_SQL` includes a strict syntax parser that blocks destructive operations like `DROP` or `DELETE` to prevent state-poisoning attacks.

---

## 👁️ 4. Observation Space

After every environment step, the server returns a `CRMPipelineObservation` object representing the current POMDP configuration.

```json
{
  "current_task_objective": "Formal string denoting the exact instruction set.",
  "schema_target": {"email": "str", "phone": "int"},
  "available_sources": ["salesforce", "web_leads"],
  "current_view": "| id | email | ...",
  "data_quality_report": "Missing values detected in 14% of fields...",
  "last_action_feedback": "Successfully dropped 5 duplicates based on EXACT_EMAIL."
}
```

---

## 📋 5. Task Catalogue

The environment dynamically spawns 3 increasingly difficult evaluation tasks defined in `openenv.yaml`.

| Task ID | Level | Objective Description |
| :---: | :---: | :--- |
| **`t1`** | 🟢 **Easy** | **Web Forms Normalization:** Clean a single dataset. Fix date formats, standardize email casing, and strip trailing white spaces. |
| **`t2`** | 🟡 **Medium** | **Legacy DB Deduplication:** Standardize and merge `web_forms` and `legacy_db` tables containing erratic schemas and conflicting uniqueness constraints. |
| **`t3`** | 🔴 **Hard** | **3-Way Enterprise Merge:** Standardize `salesforce`, `web_leads`, and `legacy_db`. The agent must use dynamic `EXECUTE_SQL` joins and filter out bot-injected outlier rows. |

---

## ⚡ 6. Setup & Installation

### Option A: Local Execution (Native Python)
1. Ensure the `uv` package manager and `openenv-core` are available.
2. Clone the repository and install dependencies natively.
```bash
uv run -m server.app
```

### Option B: Containerized Execution (Docker)
The environment ships with a production-ready OpenEnv Dockerfile.
```bash
docker build -t crm-pipeline-env .
docker run -p 8080:8080 crm-pipeline-env
```
Once initialized, the environment responds natively to `/reset`, `/step` and `/state` API specifications endpoints.

---

## 🚀 7. Baseline Inference & Reproducibility

An out-of-the-box evaluation script (`inference.py`) is provided. This script rigidly aligns with the OpenEnv validation formats and features standard deterministic fallbacks if LLM configurations rate-limit.

### Configuration
Export your API credentials before instantiating the baseline test:
```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="hf_YourTokenHere"
```

### Running the Evaluator
Run the script to reproduce deterministic scores across all three difficulty levels:
```bash
uv run python inference.py
```

### Verified Baseline Scores
| Task | Final Grade (Score) | Strategy utilized |
| :--- | :--- | :--- |
| **Task 1** | 1.000 (100%) | Rule-based Heuristic |
| **Task 2** | 1.000 (100%) | Rule-based Heuristic |
| **Task 3** | 1.000 (100%) | Rule-based Heuristic |
