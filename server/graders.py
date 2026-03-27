import pandas as pd
from server.environment import CRMDataPipelineEnv

def grade_task_1(env: CRMDataPipelineEnv) -> float:
    final_df = env.get_final_dataframe("web_forms")
    truth_df = env.get_ground_truth()
    
    if final_df.empty or truth_df is None:
        return 0.0
        
    correct_rows = 0
    for idx, truth_row in truth_df.iterrows():
        match = final_df[final_df['customer_id'] == truth_row['customer_id']]
        if not match.empty:
            agent_row = match.iloc[0]
            
            # Simple soft match for hackathon resilience
            if (str(agent_row.get('name', '')).strip() == str(truth_row.get('name', '')).strip() and
                str(agent_row.get('email', '')).lower().strip() == str(truth_row.get('email', '')).lower().strip() and
                str(agent_row.get('phone', '')).strip() == str(truth_row.get('phone', '')).strip() and
                str(agent_row.get('signup_date', '')).strip() == str(truth_row.get('signup_date', '')).strip()):
                correct_rows += 1
                
    # Severe penalty for leaving in bots or duplicates to prevent blind exploits
    penalty = max(0, len(final_df) - len(truth_df)) * 0.15
    score = (correct_rows / len(truth_df)) - penalty
    return min(1.0, max(0.0, score))

def grade_task_2(env: CRMDataPipelineEnv) -> float:
    final_df = env.get_final_dataframe("merged_output")
    truth_df = env.get_ground_truth()
    
    if final_df.empty or truth_df is None:
        return 0.0
        
    correct_rows = 0
    for idx, truth_row in truth_df.iterrows():
        match = final_df[final_df['customer_id'] == truth_row['customer_id']]
        if not match.empty and len(match) == 1:
            agent_row = match.iloc[0]
            if str(agent_row['email']).strip().lower() == str(truth_row['email']).strip().lower():
                correct_rows += 1
                
    score = correct_rows / len(truth_df)
    # Severe penalty for leaving in bots or duplicates to prevent blind exploits
    penalty = max(0, len(final_df) - len(truth_df)) * 0.15
    return min(1.0, max(0.0, score - penalty))

def grade_task_3(env: CRMDataPipelineEnv) -> float:
    final_df = env.get_final_dataframe("merged_output")
    truth_df = env.get_ground_truth()
    
    if final_df.empty or truth_df is None:
        return 0.0
        
    correct = 0
    for idx, truth_row in truth_df.iterrows():
        match = final_df[final_df['customer_id'] == truth_row['customer_id']]
        if not match.empty:
            agent_row = match.iloc[0]
            if (str(agent_row.get('email', '')).lower().strip() == str(truth_row.get('email', '')).lower().strip() and
                str(agent_row.get('phone', '')).replace("-", "") == str(truth_row.get('phone', '')).replace("-", "")):
                correct += 1
                
    score = correct / len(truth_df)
    # Severe penalty for leaving in bots or duplicates to prevent blind exploits
    penalty = max(0, len(final_df) - len(truth_df)) * 0.15
    return min(1.0, max(0.0, score - penalty))
    
def get_grader(task_id: str):
    return {"t1": grade_task_1, "t2": grade_task_2, "t3": grade_task_3}.get(task_id)

