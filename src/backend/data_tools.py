"""
Lithe — Data Science Tools (Tier 3)

Provides specialized functions for the LLM to interact with data files (CSV, Excel).
These tools are read-only and automatically execute without requiring a safeword.
"""

import os
import json
import pandas as pd
from typing import Optional

from src.backend.memory import find_file_paths, record_action
from src.backend.tools import _run_with_timeout
from src.backend.retrieval import MAX_FILE_SIZE_BYTES

def profile_data(file_path: str, conversation_id: str = "") -> str:
    """
    Reads a CSV or Excel file, profiling its contents.
    Returns summary statistics, data types, and null counts.
    
    Args:
        file_path: The filename or absolute path of the dataset.
        conversation_id: Internal parameter for logging.
    """
    print(f"[TOOL EXECUTED] profile_data: {file_path}")
    
    # 1. Resolve path using memory.py's find_file_paths
    paths = find_file_paths([os.path.basename(file_path)])
    if not paths:
        # Fallback: maybe it's an absolute path
        if os.path.exists(file_path):
            actual_path = os.path.abspath(file_path)
        else:
            record_action(
                "profile_data", 
                json.dumps({"file_path": file_path}), 
                reversible=False, 
                decision_outcome="auto-executed", 
                execution_result="failed (not found)", 
                conversation_id=conversation_id
            )
            return f"ERROR: File '{file_path}' not found in indexed directories."
    else:
        actual_path = paths[0]
        
    # 2. Check extension
    ext = os.path.splitext(actual_path)[1].lower()
    if ext not in ['.csv', '.xlsx', '.xls']:
        record_action(
            "profile_data", 
            json.dumps({"file_path": file_path}), 
            reversible=False, 
            decision_outcome="auto-executed", 
            execution_result="failed (unsupported extension)", 
            conversation_id=conversation_id
        )
        return f"ERROR: Unsupported file type '{ext}'. profile_data only supports .csv, .xlsx, and .xls."
        
    def _do_profile() -> str:
        # 3. Check file size and cap rows if necessary
        try:
            stat = os.stat(actual_path)
            size = stat.st_size
        except Exception as e:
            return f"ERROR: Could not read file info: {e}"
            
        nrows: Optional[int] = None
        is_truncated = False
        if size > MAX_FILE_SIZE_BYTES:
            nrows = 5000
            is_truncated = True
            
        # 4. Load data
        try:
            if ext == '.csv':
                df = pd.read_csv(actual_path, nrows=nrows)
            else:
                df = pd.read_excel(actual_path, nrows=nrows)
        except Exception as e:
            return f"ERROR: Pandas failed to parse the file: {e}"
            
        if df.empty:
            return f"The file '{os.path.basename(actual_path)}' is empty."
            
        # 5. Generate profile text
        output = []
        output.append(f"--- DATA PROFILE: {os.path.basename(actual_path)} ---")
        if is_truncated:
            output.append(f"WARNING: File exceeds {MAX_FILE_SIZE_BYTES/1024:.0f}KB. Profiling is limited to the first {nrows} rows.")
        
        output.append(f"\nTotal rows (analyzed): {len(df)}")
        output.append(f"Total columns: {len(df.columns)}")
        
        output.append("\n--- Data Types & Null Counts ---")
        null_counts = df.isnull().sum()
        dtypes = df.dtypes
        for col in df.columns:
            output.append(f"- {col}: {dtypes[col]} (Nulls: {null_counts[col]})")
            
        output.append("\n--- Summary Statistics (Numeric Columns) ---")
        desc = df.describe()
        if desc.empty:
            output.append("No numeric columns available to summarize.")
        else:
            output.append(desc.to_string())
            
        output.append("-" * 40)
        
        # 6. Record success
        record_action(
            "profile_data", 
            json.dumps({"file_path": actual_path, "truncated": is_truncated}), 
            reversible=False, 
            decision_outcome="auto-executed", 
            execution_result="success", 
            conversation_id=conversation_id
        )
        
        return "\n".join(output)
        
    try:
        res = _run_with_timeout(_do_profile)
        if res and res.startswith("ERROR"):
            record_action(
                "profile_data", 
                json.dumps({"file_path": actual_path}), 
                reversible=False, 
                decision_outcome="auto-executed", 
                execution_result=res, 
                conversation_id=conversation_id
            )
        return res
    except Exception as e:
        err = f"ERROR: Failed to profile data: {str(e)}"
        record_action(
            "profile_data", 
            json.dumps({"file_path": actual_path}), 
            reversible=False, 
            decision_outcome="auto-executed", 
            execution_result=err, 
            conversation_id=conversation_id
        )
        return err
