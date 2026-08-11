"""
Lithe — Data Science Tools (Tier 3)

Provides specialized functions for the LLM to interact with data files (CSV, Excel).
These tools are read-only and automatically execute without requiring a safeword.
"""

import os
import json
import base64
import io
import pandas as pd
from typing import Optional
import matplotlib
matplotlib.use('Agg')  # Set non-interactive backend before pyplot import
import matplotlib.pyplot as plt

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

def _plot_bar(df: pd.DataFrame, x: str, y: str, title: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 5))
    df.plot.bar(x=x, y=y, ax=ax, color='#4A90E2')
    ax.set_title(title or f"Bar Chart: {y} by {x}")
    plt.tight_layout()
    return fig

def _plot_line(df: pd.DataFrame, x: str, y: str, title: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 5))
    df.plot.line(x=x, y=y, ax=ax, color='#E24A4A', marker='o')
    ax.set_title(title or f"Line Chart: {y} over {x}")
    plt.tight_layout()
    return fig

def _plot_scatter(df: pd.DataFrame, x: str, y: str, title: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 5))
    df.plot.scatter(x=x, y=y, ax=ax, color='#50E3C2', alpha=0.7)
    ax.set_title(title or f"Scatter Plot: {y} vs {x}")
    plt.tight_layout()
    return fig

def _plot_hist(df: pd.DataFrame, x: str, title: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 5))
    df[x].plot.hist(ax=ax, bins=20, color='#F5A623', edgecolor='black')
    ax.set_title(title or f"Histogram of {x}")
    plt.tight_layout()
    return fig

def inline_chart(file_path: str, chart_type: str, x_column: str, y_column: str = "", title: str = "", conversation_id: str = "") -> str:
    """
    Reads a dataset and generates a base64 encoded PNG chart.
    Valid chart types: 'bar', 'line', 'scatter', 'hist'.
    """
    print(f"[TOOL EXECUTED] inline_chart: {chart_type} for {file_path}")
    
    paths = find_file_paths([os.path.basename(file_path)])
    if not paths:
        if os.path.exists(file_path):
            actual_path = os.path.abspath(file_path)
        else:
            record_action("inline_chart", json.dumps({"file_path": file_path}), reversible=False, decision_outcome="auto-executed", execution_result="failed (not found)", conversation_id=conversation_id)
            return f"ERROR: File '{file_path}' not found in indexed directories."
    else:
        actual_path = paths[0]
        
    ext = os.path.splitext(actual_path)[1].lower()
    if ext not in ['.csv', '.xlsx', '.xls']:
        record_action("inline_chart", json.dumps({"file_path": file_path}), reversible=False, decision_outcome="auto-executed", execution_result="failed (unsupported extension)", conversation_id=conversation_id)
        return f"ERROR: Unsupported file type '{ext}'. inline_chart only supports .csv, .xlsx, and .xls."
        
    def _do_chart() -> str:
        try:
            stat = os.stat(actual_path)
            size = stat.st_size
        except Exception as e:
            return f"ERROR: Could not read file info: {e}"
            
        nrows = 5000 if size > MAX_FILE_SIZE_BYTES else None
        
        try:
            if ext == '.csv':
                df = pd.read_csv(actual_path, nrows=nrows)
            else:
                df = pd.read_excel(actual_path, nrows=nrows)
        except Exception as e:
            return f"ERROR: Pandas failed to parse the file: {e}"
            
        if df.empty:
            return f"ERROR: The file '{os.path.basename(actual_path)}' is empty."
            
        # Column validation
        valid_cols = list(df.columns)
        if x_column not in valid_cols:
            return f"ERROR: Column '{x_column}' not found. Available columns: {', '.join(valid_cols)}"
        if chart_type in ['bar', 'line', 'scatter'] and y_column and y_column not in valid_cols:
            return f"ERROR: Column '{y_column}' not found. Available columns: {', '.join(valid_cols)}"
            
        # Plotting
        try:
            if chart_type == 'bar':
                fig = _plot_bar(df, x_column, y_column, title)
            elif chart_type == 'line':
                fig = _plot_line(df, x_column, y_column, title)
            elif chart_type == 'scatter':
                fig = _plot_scatter(df, x_column, y_column, title)
            elif chart_type == 'hist':
                fig = _plot_hist(df, x_column, title)
            else:
                return f"ERROR: Invalid chart_type '{chart_type}'. Must be one of: bar, line, scatter, hist."
                
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            plt.close(fig)  # Prevent memory leak
            
            b64_data = base64.b64encode(buf.getvalue()).decode('utf-8')
            data_uri = f"data:image/png;base64,{b64_data}"
            
            record_action("inline_chart", json.dumps({"file_path": actual_path, "type": chart_type}), reversible=False, decision_outcome="auto-executed", execution_result="success", conversation_id=conversation_id)
            return data_uri
        except Exception as e:
            return f"ERROR: Failed to generate chart: {e}"
            
    try:
        res = _run_with_timeout(_do_chart)
        if res and res.startswith("ERROR"):
            record_action("inline_chart", json.dumps({"file_path": actual_path}), reversible=False, decision_outcome="auto-executed", execution_result=res, conversation_id=conversation_id)
        return res
    except Exception as e:
        err = f"ERROR: Tool execution failed: {str(e)}"
        record_action("inline_chart", json.dumps({"file_path": actual_path}), reversible=False, decision_outcome="auto-executed", execution_result=err, conversation_id=conversation_id)
        return err
