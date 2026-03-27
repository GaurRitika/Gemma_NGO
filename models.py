from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import Field
from dataclasses import dataclass

try:
    from openenv.core.env_server import Action, Observation, State
except ImportError:
    # Fallbacks for strict typing if openenv-core isn't installed yet
    @dataclass
    class Action: pass
    @dataclass
    class Observation: pass
    @dataclass
    class State: pass

class StandardizationStrategy(str, Enum):
    TO_DATETIME_ISO = "TO_DATETIME_ISO"
    LOWERCASE_STRIP = "LOWERCASE_STRIP"
    EXTRACT_NUMBERS = "EXTRACT_NUMBERS"
    PHONE_E164 = "PHONE_E164"

class MissingStrategy(str, Enum):
    FILL_MEAN = "FILL_MEAN"
    FILL_MODE = "FILL_MODE"
    FILL_VALUE = "FILL_VALUE"
    DROP_ROW = "DROP_ROW"

class ConflictRule(str, Enum):
    PREFER_S1 = "PREFER_S1"
    PREFER_S2 = "PREFER_S2"
    COALESCE = "COALESCE"
    
class DeduplicationStrategy(str, Enum):
    FUZZY_NAME_PHONE = "FUZZY_NAME_PHONE"
    EXACT_EMAIL = "EXACT_EMAIL"

class PipelineActionType(str, Enum):
    VIEW_SOURCE = "VIEW_SOURCE"
    PROFILE_SOURCE = "PROFILE_SOURCE"
    STANDARDIZE_COLUMN = "STANDARDIZE_COLUMN"
    HANDLE_MISSING = "HANDLE_MISSING"
    MERGE_SOURCES = "MERGE_SOURCES"
    DEDUPLICATE = "DEDUPLICATE"
    EXECUTE_SQL = "EXECUTE_SQL"
    SUBMIT_PIPELINE = "SUBMIT_PIPELINE"

@dataclass
class CRMPipelineAction(Action):
    action_type: PipelineActionType = Field(..., description="The type of action to perform")
    source: Optional[str] = Field(None, description="The primary dataset source to act upon")
    source2: Optional[str] = Field(None, description="Secondary source for merging")
    column: Optional[str] = Field(None, description="Column to mutate")
    standardization_strategy: Optional[StandardizationStrategy] = None
    missing_strategy: Optional[MissingStrategy] = None
    deduplication_strategy: Optional[DeduplicationStrategy] = None
    fallback_value: Optional[str] = None
    join_key: Optional[str] = None
    conflict_rule: Optional[ConflictRule] = None
    final_source: Optional[str] = Field(None, description="Dataset to submit as the final pipeline result")
    query: Optional[str] = Field(None, description="Raw SQL query for EXECUTE_SQL action")
    output_table: Optional[str] = Field(None, description="Table name to write SQL output into")

@dataclass
class CRMPipelineObservation(Observation):
    done: bool
    reward: Optional[float]
    current_task_objective: str
    schema_target: Dict[str, str]
    available_sources: List[str]
    current_view: str  # Markdown table string, max 3 rows to save tokens
    data_quality_report: Optional[str] # Markdown string of quality report
    last_action_feedback: str

@dataclass
class CRMPipelineState(State):
    episode_id: Optional[str] = None
    step_count: int = 0
    task_id: str = "t1"
