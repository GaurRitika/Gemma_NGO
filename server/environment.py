import pandas as pd
import uuid
import re
from typing import Dict, Any, Optional
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
    from openenv.core.env_server import Environment
except ImportError:
    class Environment: pass

from pydantic import BaseModel

class CRMStepResult(BaseModel):
    """Standard StepResult container for OpenEnv responses."""
    observation: Any
    reward: float = 0.0
    done: bool = False

    class Config:
        arbitrary_types_allowed = True

import os
import sqlite3

# GLOBAL_TRUTH_STORE isolating the Ground Truth snapshot securely by explicit episode UUID 
GLOBAL_TRUTH_STORE: dict = {} 
# GLOBAL_ENV_STORE tracking active running pointers to the environments asynchronously
GLOBAL_ENV_STORE: dict = {} 

class CRMDataPipelineEnv(Environment):
    """
    Core POMDP Engine driving the CRM Data Pipeline operational simulation.
    Handles episodic state transitions, calculates dense heuristic rewards, and enforces data schema targets.
    """
    MIN_STEPS_BEFORE_SUBMIT = 3

    def __init__(self, **kwargs):
        self._task_id = "t1"
        self._state = CRMPipelineState(episode_id=None, step_count=0, task_id=self._task_id)
        self._sources: Dict[str, pd.DataFrame] = {}
        self._schema_target: Dict[str, str] = {}
        self._conflict_rules: Dict[str, str] = {}
        self._current_view = "No source loaded yet."
        self._last_feedback = ""
        self._report = ""
        self._last_action = None
        self._final_source_name: str = ""
        self.final_df = None
        self._last_reward = 0.0

    def reset(self) -> "CRMStepResult":
        """Reinstantiates a fresh episode securely, allocating isolated memory contexts per agent invocation."""
        task_id = os.environ.get("TASK_ID", "t1")
        print(f"DEBUG: CRMStepResult type in reset: {CRMStepResult} (id: {id(CRMStepResult)})") 
        self._task_id = task_id 
        task_data = get_task_data(task_id) 
        
        # Clone source frames strictly so Pandas mutations don't bleed across parallel episodes
        self._sources = {k: v.copy() for k, v in task_data["sources"].items()}
        self._final_source_name = ""
        
        episode_id = str(uuid.uuid4())
        
        # Key truth by episode_id → each concurrent agent gets its own immutable snapshot
        GLOBAL_TRUTH_STORE[episode_id] = {k: v.copy() for k, v in task_data["hidden_truth"].items()}
        GLOBAL_ENV_STORE[episode_id] = self
        
        self.final_df = None 
        self._schema_target = task_data["schema"] 
        self._conflict_rules = task_data.get("conflict_rules", {}) 
        
        self._state = CRMPipelineState(
            episode_id=episode_id,
            step_count=0, 
            task_id=task_id
        )
        
        self._current_view = "Select a source to view."
        self._last_feedback = f"Environment reset natively for task {task_id}. Episode UUID: {episode_id}"
        
        # Auto-profile immediately so Gemma can see columns instead of guessing
        source_name = list(self._sources.keys())[0] if self._sources else ""
        if source_name:
            df = self._sources[source_name]
            null_counts = df.isnull().sum().to_dict()
            types = df.dtypes.astype(str).to_dict()
            report = []
            for col in df.columns:
                report.append(f"- **{col}**: type={types[col]}, nulls={null_counts[col]}")
            self._report = "\n".join(report)
        else:
            self._report = None
            
        self._last_action = None
        
        self._last_action = None
        self._last_reward = 0.0
        
        obs = self._build_observation(done=False, reward=0.0) 
        return CRMStepResult(observation=obs, reward=0.0, done=False)
        
    def reset_with_dataframe(self, user_df: pd.DataFrame, source_name="user_data") -> "CRMStepResult":
        """Instantiate environment directly with a user uploaded dataset."""
        self._task_id = "real_data"
        episode_id = str(uuid.uuid4())
        
        self._sources = {source_name: user_df.copy()}
        self._final_source_name = ""
        
        GLOBAL_TRUTH_STORE[episode_id] = {} # No hidden truth for real data
        GLOBAL_ENV_STORE[episode_id] = self
        
        self.final_df = None 
        # Attempt to infer a very generic schema target based on columns
        self._schema_target = {col: "string" for col in user_df.columns} 
        self._conflict_rules = {} 
        
        self._state = CRMPipelineState(
            episode_id=episode_id,
            step_count=0, 
            task_id="real_data"
        )
        
        self._current_view = "Select a source to view."
        self._last_feedback = f"Environment reset natively for Real Mode upload. Episode UUID: {episode_id}"
        
        # Auto-profile immediately so Gemma can see columns instead of guessing
        df = self._sources[source_name]
        null_counts = df.isnull().sum().to_dict()
        types = df.dtypes.astype(str).to_dict()
        report = []
        for col in df.columns:
            report.append(f"- **{col}**: type={types[col]}, nulls={null_counts[col]}")
        self._report = "\n".join(report)
        
        self._last_action = None
        
        obs = self._build_observation(done=False, reward=0.0) 
        return CRMStepResult(observation=obs, reward=0.0, done=False)

    def step(self, action: CRMPipelineAction) -> "CRMStepResult": 
        """Executes a parsed JSON payload synchronously within the data engineering POMDP scope."""
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
            elif action.action_type == PipelineActionType.EXECUTE_SQL:
                reward += self._handle_sql(action)
            elif action.action_type == PipelineActionType.SUBMIT_PIPELINE:
                if self._state.step_count < self.MIN_STEPS_BEFORE_SUBMIT:
                    reward = -0.15
                    self._last_feedback = f"Early submission blocked. You must perform at least {self.MIN_STEPS_BEFORE_SUBMIT} cleaning steps (Profile, Standardize, etc.) before submitting."
                    done = False
                else:
                    done = True
                    self._final_source_name = action.final_source or ""
                    self.final_df = self._sources.get(self._final_source_name, None)
                    # Final submission bonus based on schema match (heuristic)
                    df = self.get_final_dataframe()
                    schema_match_ratio = len([c for c in self._schema_target if c in df.columns]) / max(1, len(self._schema_target))
                    reward = 0.2 * schema_match_ratio
                    self._last_feedback = f"Pipeline submitted with final source: {action.final_source}."
            else:
                self._last_feedback = "Unknown action type."
                reward = -0.05
        except Exception as e:
            self._last_feedback = f"Error: {str(e)}"
            self._last_feedback = f"Error: {str(e)}"
            reward = -0.05
            
        self._last_reward = reward
        obs = self._build_observation(done=done, reward=reward)
        return CRMStepResult(observation=obs, reward=reward, done=done)
        
    async def reset_async(self) -> "CRMStepResult":
        return self.reset()
        
    async def step_async(self, action: CRMPipelineAction) -> "CRMStepResult":
        return self.step(action=action)
        

    def _build_observation(self, done: bool, reward: float) -> CRMPipelineObservation:
        objective = {
            "t1": "Normalize donation_forms dataset",
            "t2": "Deduplicate legacy_ngo_db dataset",
            "t3": "Merge Volunteer Portal, Donation Forms, Legacy NGO databases",
            "real_data": "Clean and format custom uploaded dataset"
        }.get(self._task_id, "Unknown task")

        # ── Always regenerate the quality report from ALL sources (live) ──
        # This ensures Gemma sees dirty columns across every table, not just
        # a stale snapshot from the initial reset.
        all_reports = []
        for src_name, df in self._sources.items():
            null_counts = df.isnull().sum().to_dict()
            types = df.dtypes.astype(str).to_dict()
            all_reports.append(f"### Source: {src_name} ({len(df)} rows)")
            for col in df.columns:
                all_reports.append(
                    f"- **{col}**: type={types[col]}, nulls={null_counts[col]}"
                )
        live_report = "\n".join(all_reports)

        # Also expose a sample of the first/primary source for context
        primary_src = list(self._sources.keys())[0] if self._sources else ""
        df_target = self._sources.get(primary_src, pd.DataFrame())
        dynamic_view = df_target.head(3).to_dict(orient="records") if not df_target.empty else "No records"

        return CRMPipelineObservation(
            done=done,
            reward=reward,
            current_task_objective=objective,
            schema_target=self._schema_target,
            available_sources=list(self._sources.keys()),
            current_view=str(dynamic_view),
            data_quality_report=live_report,
            last_action_feedback=self._last_feedback,
            conflict_rules=self._conflict_rules if self._conflict_rules else None
        )
        
    @property
    def state(self) -> CRMPipelineState:
        return self._state
        
    def get_episode_truth(self) -> dict:
        """Return the truth snapshot for this episode (keyed by episode_id)."""
        return GLOBAL_TRUTH_STORE.get(self._state.episode_id, {})

    def get_final_dataframe(self, final_source_name: str = "") -> pd.DataFrame:
        """Return the submitted final dataframe. Falls back to self._final_source_name."""
        name = final_source_name or self._final_source_name
        return self._sources.get(name, pd.DataFrame())
            
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
        
        # VALIDATION: Prevent wrong strategy application
        col_lower = col.lower()
        
        # Detect email columns
        if any(keyword in col_lower for keyword in ['email', 'e-mail', 'mail', 'contact']):
            if strat in ["EXTRACT_NUMBERS", StandardizationStrategy.EXTRACT_NUMBERS.value]:
                self._last_feedback = f"BLOCKED: Cannot use EXTRACT_NUMBERS on email column '{col}'. Use LOWERCASE_STRIP instead!"
                return -0.2
            if strat in ["TO_DATETIME_ISO", StandardizationStrategy.TO_DATETIME_ISO.value]:
                self._last_feedback = f"BLOCKED: Cannot use TO_DATETIME_ISO on email column '{col}'. Use LOWERCASE_STRIP instead!"
                return -0.2
        
        # Detect phone columns
        if any(keyword in col_lower for keyword in ['phone', 'mobile', 'tel', 'contact_number']):
            if strat in ["TO_DATETIME_ISO", StandardizationStrategy.TO_DATETIME_ISO.value]:
                self._last_feedback = f"BLOCKED: Cannot use TO_DATETIME_ISO on phone column '{col}'. Use EXTRACT_NUMBERS instead!"
                return -0.2
        
        # Detect date columns
        if any(keyword in col_lower for keyword in ['date', 'time', 'created', 'updated', 'signup', 'registration']):
            if strat in ["EXTRACT_NUMBERS", StandardizationStrategy.EXTRACT_NUMBERS.value]:
                self._last_feedback = f"BLOCKED: Cannot use EXTRACT_NUMBERS on date column '{col}'. Use TO_DATETIME_ISO instead!"
                return -0.2
        
        # Detect name columns
        if any(keyword in col_lower for keyword in ['name', 'donor', 'volunteer', 'contact', 'person']):
            if strat in ["EXTRACT_NUMBERS", StandardizationStrategy.EXTRACT_NUMBERS.value]:
                self._last_feedback = f"BLOCKED: Cannot use EXTRACT_NUMBERS on name column '{col}'. Use LOWERCASE_STRIP instead!"
                return -0.2
            if strat in ["TO_DATETIME_ISO", StandardizationStrategy.TO_DATETIME_ISO.value]:
                self._last_feedback = f"BLOCKED: Cannot use TO_DATETIME_ISO on name column '{col}'. Use LOWERCASE_STRIP instead!"
                return -0.2
        
        # Heuristic reward: measure how many values changed to "better" format
        # without leaking Ground Truth.
        change_count = 0
        total_rows = len(df)
        
        if strat == StandardizationStrategy.LOWERCASE_STRIP.value or strat == "LOWERCASE_STRIP":
            # Check if strings are already lowercase/stripped
            pre_clean = df[col].astype(str).str.contains(r'[A-Z]|\s+$|^\s+', regex=True).sum()
            
            # Special handling for email columns - preserve @ and domain
            if any(keyword in col_lower for keyword in ['email', 'e-mail', 'mail']):
                def clean_email(email):
                    if pd.isna(email) or email is None or str(email).strip() == '':
                        return ""
                    email_str = str(email).strip().lower()
                    # Remove any spaces around @ symbol
                    email_str = email_str.replace(' @ ', '@').replace('@ ', '@').replace(' @', '@')
                    # Basic validation: must contain @ and a dot after @
                    if '@' in email_str and '.' in email_str.split('@')[-1]:
                        return email_str
                    return ""  # Invalid email format
                df[col] = df[col].apply(clean_email)
            else:
                # Standard text cleaning for names, addresses, etc.
                df[col] = df[col].astype(str).str.lower().str.strip()
            
            change_count = pre_clean
        elif strat == StandardizationStrategy.EXTRACT_NUMBERS.value or strat == "EXTRACT_NUMBERS":
            # Check for non-digit characters in phone (excluding + prefix)
            pre_clean = df[col].astype(str).str.contains(r'[^\d+]', regex=True).sum()
            def to_e164(p):
                if pd.isna(p) or p is None:
                    return ""
                s = str(p).strip().lower()
                
                # Handle extensions
                if 'ext' in s or 'x' in s:
                    s = s.split('ext')[0].split('x')[0]
                
                # Extract all digits
                digits = re.sub(r'\D+', '', s)
                
                # If no digits found, return empty
                if not digits:
                    return ""
                
                # If digits are too short (less than 7), likely invalid
                if len(digits) < 7:
                    return ""
                
                # Add + prefix for E.164 format
                return "+" + digits
            
            df[col] = df[col].apply(to_e164)
            change_count = pre_clean
        elif strat == StandardizationStrategy.TO_DATETIME_ISO.value or strat == "TO_DATETIME_ISO":
            pre_clean = df[col].astype(str).str.contains(r'/', regex=True).sum() # common dirty separator
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%dT00:00:00').fillna("")
            change_count = pre_clean
        else:
            self._last_feedback = f"CRITICAL ERROR: Strategy '{strat}' does not exist! You MUST use LOWERCASE_STRIP, EXTRACT_NUMBERS, or TO_DATETIME_ISO."
            return -0.2
            
        if change_count == 0:
            self._last_feedback = f"ERROR: Column '{col}' is already perfectly clean! Do NOT touch '{col}' again. Choose a different column based on the data_quality_report."
            return -0.1
            
        self._last_feedback = f"Standardized {action.source}.{col} using {strat}. Fixed {change_count} rows."
        improvement_ratio = change_count / max(1, total_rows)
        return min(0.05, 0.02 + (improvement_ratio * 0.1))

    def _handle_missing(self, action: CRMPipelineAction) -> float:
        df = self._get_df(action.source)
        col = self._get_col(df, action.column)
        strat = action.missing_strategy
        
        null_count_before = df[col].isnull().sum()
        if strat == MissingStrategy.DROP_ROW:
            df.dropna(subset=[col], inplace=True)
            reward = (null_count_before / max(1, len(df) + null_count_before)) * 0.1
        elif strat == MissingStrategy.FILL_VALUE:
            df[col].fillna(action.fallback_value, inplace=True)
            reward = (null_count_before / max(1, len(df))) * 0.05
            
        if null_count_before == 0:
            self._last_feedback = f"Error: No missing values found in {action.source}.{col}. Penalty applied! Pick a different column."
            return -0.1
            
        self._last_feedback = f"Handled {null_count_before} missing values in {action.source}.{col}"
        return max(0.01, reward)

    def _handle_deduplicate(self, action: CRMPipelineAction) -> float:
        df = self._get_df(action.source)
        start_len = len(df)
        
        if action.deduplication_strategy == DeduplicationStrategy.EXACT_EMAIL:
             email_cols = [c for c in df.columns if 'email' in c.lower() or 'e-mail' in c.lower() or 'mail' in c.lower()]
             col = email_cols[0] if email_cols else (action.column if action.column in df.columns else None)
             if not col:
                 self._last_feedback = f"Error: No email column found for EXACT_EMAIL deduplication in {action.source}. Choose another action."
                 return -0.1
             df.drop_duplicates(subset=[col], inplace=True)
        elif action.deduplication_strategy == DeduplicationStrategy.FUZZY_NAME_PHONE:
             name_cols = [c for c in df.columns if 'name' in c.lower() or 'donor' in c.lower()]
             phone_cols = [c for c in df.columns if 'phone' in c.lower() or 'mobile' in c.lower()]
             if not name_cols or not phone_cols:
                 self._last_feedback = f"Error: Name or phone columns missing for FUZZY_NAME_PHONE deduplication in {action.source}. Choose another action."
                 return -0.1
             df["_tmp_name"] = df[name_cols[0]].astype(str).str.lower().str.strip()
             df["_tmp_phone"] = df[phone_cols[0]].astype(str).str.replace(r'\D+', '', regex=True)
             df.drop_duplicates(subset=["_tmp_name", "_tmp_phone"], inplace=True)
             df.drop(columns=["_tmp_name", "_tmp_phone"], inplace=True)
             
        removed = start_len - len(df)
        self._sources[action.source] = df # Save it back
        if removed == 0:
            self._last_feedback = f"Error: No duplicates found in {action.source} using {action.deduplication_strategy}. Penalty applied! Move to a different action."
            return -0.1
            
        self._last_feedback = f"Deduplicated {action.source}, removed {removed} rows."
        return (removed / max(1, start_len)) * 0.2

    def _handle_merge(self, action: CRMPipelineAction) -> float:
         df1 = self._get_df(action.source).copy()
         df2 = self._get_df(action.source2).copy()
         
         key = action.join_key
         if key not in df1.columns or key not in df2.columns:
             self._last_feedback = f"Merge failed: key '{key}' missing from one of the sources."
             return -0.05

         # Realistic "fuzzy" prep: normalize join keys
         df1[key] = df1[key].astype(str).str.lower().str.strip()
         df2[key] = df2[key].astype(str).str.lower().str.strip()
         
         merged = pd.merge(df1, df2, on=key, how="outer", suffixes=('_s1', '_s2'))
         
         # Resolve conflicts and COALESCE
         for col in list(merged.columns):
             if col.endswith('_s1'):
                 base_col = col[:-3]
                 s1_col, s2_col = base_col + '_s1', base_col + '_s2'
                 
                 if s2_col in merged.columns:
                     if action.conflict_rule == ConflictRule.PREFER_S1:
                         merged[base_col] = merged[s1_col].combine_first(merged[s2_col])
                     elif action.conflict_rule == ConflictRule.PREFER_S2:
                         merged[base_col] = merged[s2_col].combine_first(merged[s1_col])
                     else: # Default COALESCE
                         merged[base_col] = merged[s1_col].combine_first(merged[s2_col])
                     merged.drop(columns=[s1_col, s2_col], inplace=True)
                  
         self._sources["merged_output"] = merged
         self._last_feedback = f"Merged {action.source} and {action.source2} into 'merged_output' using {key}."
         return 0.05
        
    def _handle_sql(self, action: CRMPipelineAction) -> float:
        conn = sqlite3.connect(":memory:")
        for name, df in self._sources.items():
            # Convert dicts/lists to strings for SQL insertion if any exist
            clean_df = df.copy()
            for col in clean_df.columns:
                if clean_df[col].dtype == object:
                    clean_df[col] = clean_df[col].astype(str)
            clean_df.to_sql(name, conn, index=False, if_exists='replace')
            
        try:
            # SQL Injection Hardening
            query_stripped = action.query.strip().upper()
            if not query_stripped.startswith("SELECT "):
                self._last_feedback = "Blocked Action: Only SELECT queries are allowed for security."
                return -0.1

            forbidden = ["DROP ", "DELETE ", "UPDATE ", "INSERT ", "ALTER ", "CREATE ", "TRUNCATE "]
            if any(cmd in query_stripped for cmd in forbidden):
                self._last_feedback = f"Blocked: Query contains forbidden keyword."
                return -0.1

            result_df = pd.read_sql_query(action.query, conn)
            out_name = action.output_table if action.output_table else "sql_output"
            self._sources[out_name] = result_df
            self._last_feedback = f"Executed SQL successfully. Wrote {len(result_df)} rows to '{out_name}'."
            return 0.1
        except Exception as e:
            self._last_feedback = f"SQL Error: {str(e)}"
            return -0.1
        finally:
            conn.close()

    def _get_df(self, source: str) -> pd.DataFrame:
        if not source or source not in self._sources:
            raise ValueError(f"Source '{source}' not found. Available: {list(self._sources.keys())}")
        return self._sources[source]
        
    def _get_col(self, df: pd.DataFrame, col: str) -> str:
        if not col or col not in df.columns:
            raise ValueError(f"Column '{col}' not found. Available: {list(df.columns)}")
        return col

