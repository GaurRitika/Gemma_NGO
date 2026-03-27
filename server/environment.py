import pandas as pd
import uuid
import re
from typing import Dict
from models import (
    CRMPipelineAction, 
    CRMPipelineObservation, 
    CRMPipelineState,
    PipelineActionType,
    StandardizationStrategy,
    MissingStrategy,
    ConflictRule,
    DeduplicationStrategy
)
from server.data_generator import get_task_data

try:
    from openenv.core.env_server import Environment, StepResult
except ImportError:
    # Stub it for type checking if openenv not fully installed yet locally
    class Environment: pass
    class StepResult:
        def __init__(self, observation, reward, done):
            self.observation = observation
            self.reward = reward
            self.done = done

import os

LAST_ENV_INSTANCE = {}

class CRMDataPipelineEnv(Environment):
    def __init__(self, **kwargs):
        self._task_id = os.environ.get("CURRENT_TASK_ID", "t1")
        LAST_ENV_INSTANCE[self._task_id] = self
        self._state = CRMPipelineState(episode_id=None, step_count=0, task_id=self._task_id)
        self._sources: Dict[str, pd.DataFrame] = {}
        self._ground_truth: Dict[str, pd.DataFrame] = {}
        self._schema_target: Dict[str, str] = {}
        self._current_view = "No source loaded yet."
        self._last_feedback = ""
        self._report = ""
        self._last_action = None

    def reset(self, task_id: str = "t1") -> StepResult:
        self._task_id = task_id
        task_data = get_task_data(task_id)
        
        # We must clone these dataframes so mutations don't bleed across episodes
        self._sources = {k: v.copy() for k, v in task_data["sources"].items()}
        self._ground_truth = {k: v.copy() for k, v in task_data["hidden_truth"].items()}
        self._schema_target = task_data["schema"]
        
        self._state = CRMPipelineState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            task_id=task_id
        )
        
        self._current_view = "Select a source to view."
        self._last_feedback = f"Environment reset for task {task_id}."
        self._report = None
        self._last_action = None
        
        obs = self._build_observation(done=False, reward=0.0)
        return StepResult(observation=obs, reward=0.0, done=False)
        
    def step(self, action: CRMPipelineAction) -> StepResult:
        self._state.step_count += 1
        reward = 0.0
        done = False
        self._last_action = action
        
        try:
            if action.action_type == PipelineActionType.VIEW_SOURCE:
                self._handle_view_source(action)
            elif action.action_type == PipelineActionType.PROFILE_SOURCE:
                self._handle_profile(action)
                reward = 0.02
            elif action.action_type == PipelineActionType.STANDARDIZE_COLUMN:
                reward += self._handle_standardize(action)
            elif action.action_type == PipelineActionType.HANDLE_MISSING:
                reward += self._handle_missing(action)
            elif action.action_type == PipelineActionType.DEDUPLICATE:
                reward += self._handle_deduplicate(action)
            elif action.action_type == PipelineActionType.MERGE_SOURCES:
                reward += self._handle_merge(action)
            elif action.action_type == PipelineActionType.SUBMIT_PIPELINE:
                done = True
                self._last_feedback = f"Pipeline submitted with final source: {action.final_source}."
            else:
                self._last_feedback = "Unknown action type."
                reward = -0.05
        except Exception as e:
            self._last_feedback = f"Error: {str(e)}"
            reward = -0.05
            
        obs = self._build_observation(done=done, reward=reward)
        return StepResult(observation=obs, reward=reward, done=done)
        
    def _build_observation(self, done: bool, reward: float) -> CRMPipelineObservation:
        objective = {
            "t1": "Normalize web_forms dataset",
            "t2": "Deduplicate legacy_db dataset",
            "t3": "Merge Salesforce, Web Leads, Legacy databases"
        }.get(self._task_id, "Unknown task")
        
        return CRMPipelineObservation(
            done=done,
            reward=reward,
            current_task_objective=objective,
            schema_target=self._schema_target,
            available_sources=list(self._sources.keys()),
            current_view=self._current_view,
            data_quality_report=self._report if self._report else "",
            last_action_feedback=self._last_feedback
        )
        
    @property
    def state(self) -> CRMPipelineState:
        return self._state
        
    def get_final_dataframe(self, final_source_name: str) -> pd.DataFrame:
        """Helper for the grader to retrieve the final dataframe"""
        return self._sources.get(final_source_name, pd.DataFrame())
        
    def get_ground_truth(self) -> pd.DataFrame:
        """Helper for the grader to get the expected final dataframe."""
        if self._task_id == "t3":
            return self._ground_truth.get("merged_final")
        elif self._task_id == "t2":
            return self._ground_truth.get("legacy_db")
        else:
            return self._ground_truth.get("web_forms")
            
    # -- ACTION HANDLERS --
    
    def _handle_view_source(self, action: CRMPipelineAction):
        df = self._get_df(action.source)
        self._current_view = df.head(3).to_markdown()
        self._last_feedback = f"Viewing top 3 rows of {action.source}"
        
    def _handle_profile(self, action: CRMPipelineAction):
        df = self._get_df(action.source)
        null_counts = df.isnull().sum().to_dict()
        types = df.dtypes.astype(str).to_dict()
        report = []
        for col in df.columns:
            report.append(f"- **{col}**: type={types[col]}, nulls={null_counts[col]}")
        self._report = "\n".join(report)
        self._last_feedback = f"Profiled {action.source}"
        
    def _handle_standardize(self, action: CRMPipelineAction) -> float:
        df = self._get_df(action.source)
        col = self._get_col(df, action.column)
        strat = action.standardization_strategy
        
        # Clone before mutation to check correctness
        old_series = df[col].copy()
        
        if strat == StandardizationStrategy.LOWERCASE_STRIP:
            df[col] = df[col].astype(str).str.lower().str.strip()
        elif strat == StandardizationStrategy.EXTRACT_NUMBERS:
            def to_e164(p):
                if pd.isna(p) or p is None: return ""
                s = str(p).lower()
                if 'ext' in s or 'x' in s:
                    s = s.split('ext')[0].split('x')[0]
                digits = re.sub(r'\D+', '', s)
                if not digits: return ""
                return "+" + digits if not s.startswith("+") else "+" + digits
            df[col] = df[col].apply(to_e164)
        elif strat == StandardizationStrategy.TO_DATETIME_ISO:
            # We force it into typical ISO format YYYY-MM-DD string, invalid dates become empty strings
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%dT00:00:00').fillna("")
            
        self._last_feedback = f"Standardized {action.source}.{col} using {strat}"
        
        # Partial reward: +0.05 if it now matches ground truth better than before
        truth_df = self._get_truth(action.source)
        if truth_df is not None and col in truth_df.columns:
            # Drop nulls for comparison count
            old_correct = (old_series == truth_df[col]).sum()
            new_correct = (df[col] == truth_df[col]).sum()
            if new_correct > old_correct:
                return 0.05
            elif new_correct < old_correct:
                # Agent ruined valid data!
                return -0.05
        return 0.0

    def _handle_missing(self, action: CRMPipelineAction) -> float:
        df = self._get_df(action.source)
        col = self._get_col(df, action.column)
        strat = action.missing_strategy
        
        null_count_before = df[col].isnull().sum()
        if strat == MissingStrategy.DROP_ROW:
            df.dropna(subset=[col], inplace=True)
        elif strat == MissingStrategy.FILL_VALUE:
            df[col].fillna(action.fallback_value, inplace=True)
            
        self._last_feedback = f"Handled {null_count_before} missing values in {action.source}.{col}"
        # Small positive reward for removing missing data, though Grader cares about truth mostly
        return 0.01

    def _handle_deduplicate(self, action: CRMPipelineAction) -> float:
        df = self._get_df(action.source)
        start_len = len(df)
        
        if action.deduplication_strategy == DeduplicationStrategy.EXACT_EMAIL:
             df.drop_duplicates(subset=["email"], inplace=True)
        elif action.deduplication_strategy == DeduplicationStrategy.FUZZY_NAME_PHONE:
             # Basic fuzzy proxy: lowercase strip name and extract number phone match
             df["_tmp_name"] = df["name"].astype(str).str.lower().str.strip()
             df["_tmp_phone"] = df["phone"].astype(str).str.replace(r'\D+', '', regex=True)
             df.drop_duplicates(subset=["_tmp_name", "_tmp_phone"], inplace=True)
             df.drop(columns=["_tmp_name", "_tmp_phone"], inplace=True)
             
        self._sources[action.source] = df # Save it back
        self._last_feedback = f"Deduplicated {action.source}, removed {start_len - len(df)} rows."
        
        truth_len = len(self._get_truth(action.source)) if self._get_truth(action.source) is not None else start_len
        # If they got closer to truth length without going under
        if len(df) >= truth_len and len(df) < start_len:
             return 0.05
        return 0.0

    def _handle_merge(self, action: CRMPipelineAction) -> float:
         df1 = self._get_df(action.source)
         df2 = self._get_df(action.source2)
         
         merged = pd.merge(df1, df2, on=action.join_key, how="outer", suffixes=('_s1', '_s2'))
         
         # Resolve conflict
         for col in merged.columns:
             if col.endswith('_s1'):
                 base_col = col[:-3]
                 s1_col, s2_col = base_col + '_s1', base_col + '_s2'
                 if action.conflict_rule == ConflictRule.PREFER_S1:
                     merged[base_col] = merged[s1_col].combine_first(merged[s2_col])
                 elif action.conflict_rule == ConflictRule.PREFER_S2:
                     merged[base_col] = merged[s2_col].combine_first(merged[s1_col])
                 merged.drop(columns=[s1_col, s2_col], inplace=True)
                 
         self._sources["merged_output"] = merged
         self._last_feedback = f"Merged {action.source} and {action.source2} into 'merged_output'"
         return 0.05
        
    def _get_df(self, source: str) -> pd.DataFrame:
        if not source or source not in self._sources:
            raise ValueError(f"Source '{source}' not found. Available: {list(self._sources.keys())}")
        return self._sources[source]
        
    def _get_truth(self, source: str) -> pd.DataFrame:
        return self._ground_truth.get(source)
        
    def _get_col(self, df: pd.DataFrame, col: str) -> str:
        if not col or col not in df.columns:
            raise ValueError(f"Column '{col}' not found. Available: {list(df.columns)}")
        return col

