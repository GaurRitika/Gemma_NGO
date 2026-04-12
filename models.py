from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

try:
    from openenv.core.env_server import Action, Observation, State
except ImportError:
    class Action(BaseModel): pass
    class Observation(BaseModel): pass
    class State(BaseModel): pass


class StandardizationStrategy(str, Enum):
    """Available strategies for deterministic column standardization."""
    TO_DATETIME_ISO = "TO_DATETIME_ISO"
    LOWERCASE_STRIP = "LOWERCASE_STRIP"
    EXTRACT_NUMBERS = "EXTRACT_NUMBERS"
    PHONE_E164 = "PHONE_E164"

class MissingStrategy(str, Enum):
    """Strategies to resolve null gaps within structured data."""
    FILL_MEAN = "FILL_MEAN"
    FILL_MODE = "FILL_MODE"
    FILL_VALUE = "FILL_VALUE"
    DROP_ROW = "DROP_ROW"

class ConflictRule(str, Enum):
    """Conflict resolution rules for handling overlapping primary keys during joins."""
    PREFER_S1 = "PREFER_S1"
    PREFER_S2 = "PREFER_S2"
    COALESCE = "COALESCE"
    
class DeduplicationStrategy(str, Enum):
    """Heuristics applied for stripping identical rows logically."""
    FUZZY_NAME_PHONE = "FUZZY_NAME_PHONE"
    EXACT_EMAIL = "EXACT_EMAIL"


class PipelineActionType(str, Enum):
    """Defines the discrete action space executable by the generic agent."""
    VIEW_SOURCE = "VIEW_SOURCE"
    PROFILE_SOURCE = "PROFILE_SOURCE"
    STANDARDIZE_COLUMN = "STANDARDIZE_COLUMN"
    HANDLE_MISSING = "HANDLE_MISSING"
    MERGE_SOURCES = "MERGE_SOURCES"
    DEDUPLICATE = "DEDUPLICATE"
    EXECUTE_SQL = "EXECUTE_SQL"
    SUBMIT_PIPELINE = "SUBMIT_PIPELINE"


class CRMPipelineAction(Action):
    """
    CRMPipelineAction establishes the JSON payload schema sent by the agent 
    to trigger state mutations within the environment. All fields dynamically 
    dictate the underlying Pandas transformations.
    """
    action_type: PipelineActionType = Field(..., description="The exact operational method to execute over the data context")
    source: Optional[str] = Field(None, description="The primary schema table or dataset source to reference")
    source2: Optional[str] = Field(None, description="Secondary schema structure needed for merge operations")
    column: Optional[str] = Field(None, description="The specific column attribute to aggressively mutate")
    standardization_strategy: Optional[StandardizationStrategy] = None
    missing_strategy: Optional[MissingStrategy] = None
    deduplication_strategy: Optional[DeduplicationStrategy] = None
    fallback_value: Optional[str] = None
    join_key: Optional[str] = None
    conflict_rule: Optional[ConflictRule] = None
    final_source: Optional[str] = Field(None, description="Dataset designated as the final pipeline result ready for external evaluation")
    query: Optional[str] = Field(None, description="Raw SQL query string used specifically during EXECUTE_SQL tasks")
    output_table: Optional[str] = Field(None, description="Target aliased table name to cache standard SQL outputs")


class CRMPipelineObservation(Observation):
    """
    CRMPipelineObservation represents the responsive payload returned directly 
    by the server after each stepwise execution. It exposes POMDP visibility,
    providing the crucial data signals the agent needs for ongoing inference.
    """
    done: bool
    reward: Optional[float]
    current_task_objective: str
    schema_target: Dict[str, str]
    available_sources: List[str]
    current_view: str 
    data_quality_report: Optional[str]
    last_action_feedback: str
    conflict_rules: Optional[Dict[str, str]] = Field(
        None,
        description="Per-column schema priority maps utilized heavily in Task 3 resolution"
    )

class CRMPipelineState(State):
    """Tracks global progression and deterministic boundaries within the episodic environment session."""
    episode_id: Optional[str] = None
    step_count: int = 0
    task_id: str = "t1"
