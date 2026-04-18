import pandas as pd
from server.environment import CRMDataPipelineEnv

def evaluate_dataframes(truth_df: pd.DataFrame, final_df: pd.DataFrame, join_key="donor_id") -> float:
    if final_df.empty or truth_df is None or truth_df.empty:
        return 0.01
        
    try:
        # We enforce uniqueness on the join key to prevent Cartesian explosion during merge if agent failed to dedup
        eval_df = final_df.drop_duplicates(subset=[join_key])
        merged = pd.merge(truth_df, eval_df, on=join_key, suffixes=('_truth', '_agent'), how='left')
    except Exception:
        # If join fails due to missing keys or type mismatch
        return 0.01
        
    num_truth_rows = len(truth_df)
    
    # Vectorized match
    for col in truth_df.columns:
        if col == join_key: 
            continue
            
        col_truth = f"{col}_truth"
        col_agent = f"{col}_agent"
        
        if col_agent not in merged.columns and col not in final_df.columns:
            # Missing column entirely
            return 0.01
            
        # If the merge didn't suffix it (because truth_df only had the column), fetch original name
        actual_col_agent = col_agent if col_agent in merged.columns else col
            
        # Treat NaNs and Nones as empty strings for safe rigorous string matching
        s_truth = merged[col_truth].fillna("").astype(str).str.strip().str.lower()
        s_agent = merged[actual_col_agent].fillna("").astype(str).str.strip().str.lower()
        
        # Exact match per column is required. 
        # Since Truth already formats Dates as ISO-8601 and Phones as E.164, 
        # this safely and strictly forces the agent to output *exactly* those formats.
        merged[f"{col}_match"] = (s_truth == s_agent)
        
    # A row is completely correct if ALL individual column matches are True
    match_cols = [f"{col}_match" for col in truth_df.columns if col != join_key]
    merged['row_correct'] = merged[match_cols].all(axis=1)
    
    correct_rows = merged['row_correct'].sum()
    score = correct_rows / num_truth_rows
    
    # Severe penalty for leaving in bots or duplicated junk rows
    penalty = max(0, len(final_df) - num_truth_rows) * 0.15
    return min(0.99, max(0.01, score - penalty))

def _grade(env: CRMDataPipelineEnv, truth_key: str, final_source: str) -> float:
    """
    Grade using the truth snapshot captured at episode reset time.
    No data regeneration — truth is always consistent with what the agent saw.
    """
    episode_truth = env.get_episode_truth()
    truth_df = episode_truth.get(truth_key)
    if truth_df is None:
        return 0.01
    final_df = env.get_final_dataframe(final_source)
    return evaluate_dataframes(truth_df, final_df)

def grade_task_1(env: CRMDataPipelineEnv) -> float:
    return _grade(env, "donation_forms", "donation_forms")

def grade_task_2(env: CRMDataPipelineEnv) -> float:
    return _grade(env, "merged_output", "merged_output")

def grade_task_3(env: CRMDataPipelineEnv) -> float:
    return _grade(env, "merged_output", "merged_output")

def get_grader(task_id: str):
    return {"t1": grade_task_1, "t2": grade_task_2, "t3": grade_task_3}.get(task_id)
