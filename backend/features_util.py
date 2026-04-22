
import pandas as pd
import numpy as np
from typing import Any,Dict
import json
from math import log2
import os


def events_to_dataframe(json_data: Any) -> pd.DataFrame:
    """
    Convert raw JSON events to DataFrame.
    
    Args:
        json_data: Either a dict with 'events' key or list of events
    
    Returns:
        DataFrame with columns: t, f, d, o, l, s, k
    """
    # Handle different input formats
    if isinstance(json_data, dict) and 'events' in json_data:
        events = json_data['events']
    elif isinstance(json_data, list):
        events = json_data
    else:
        raise ValueError("Input must be dict with 'events' key or list of events")
    
    if not events:
        return pd.DataFrame(columns=['t', 'f', 'd', 'o', 'l', 's', 'k'])
    
    df = pd.DataFrame(events)
    
    # Ensure required columns exist and have correct types
    required_columns = ['t', 'f', 'd', 'o', 'l', 's', 'k']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
        
        # Convert numeric columns
        if col in ['t', 'f', 'd', 'o', 'l']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df


def create_sliding_windows(df, window_size, step_size):
    """
    Create sliding windows from a pandas DataFrame.

    Parameters:
        df (pd.DataFrame): Input dataframe (events)
        window_size (int): Number of rows per window
        step_size (int): Step size for sliding
        step = window / 5 for 80%  overlap

    Returns:
        list of DataFrames (each window)
    """
    df = df[df["s"] != "u"].reset_index(drop=True)
    n = len(df)
    windows = []
    
    # Case 1: small session → take full data
    if n <= window_size:
        windows.append(df.copy())
        return windows
    
    # Case 2: normal sliding
    for start in range(0, n - window_size + 1, step_size):
        window = df.iloc[start:start + window_size].copy()
        windows.append(window)
    
    # Case 3: ensure full coverage (last window)
    if (n - window_size) % step_size != 0:
        last_window = df.iloc[n - window_size:n].copy()
        windows.append(last_window)
    
    return windows
    
def calculate_mean_dwell_time(window:pd.DataFrame)->float:
    return window['d'].mean()
def calcultate_std_flight_time(window:pd.DataFrame)->float:
    if len(window)<=1:
        return 0.0
    return window['f'].std()
def calculate_typing_velocity(window: pd.DataFrame) -> float:
    """
    Calculate typing velocity in CPS (characters per second).
    CPS = sum(l) / window_duration_seconds
    """
    total_characters = window['l'].sum()
    
    # Window duration: difference between last and first timestamp
    if len(window) > 1:
        window_duration_ms = window['t'].iloc[-1] - window['t'].iloc[0]
        window_duration_sec = max(window_duration_ms / 1000.0, 0.001)  # Avoid division by zero
    else:
        window_duration_sec = window['d'].iloc[0] / 1000.0 if len(window) > 0 else 0.001
    
    return total_characters / window_duration_sec
def calculate_correction_rate(window: pd.DataFrame) -> float:
    """Calculate correction rate (count of backspace / window size).""" 
    backspace_count = (window['k'] == 'backspace').sum()
    return backspace_count / len(window)
def calculate_burst_ratio(window: pd.DataFrame) -> float:
    """Calculate burst ratio (count of keys with length > 1 / window size)."""
    burst_count = (window['l'] > 1).sum()
    return burst_count / len(window)
def calculate_max_burst_length(window:pd.DataFrame)->int:
    return window['l'].max()
def calculate_bulk_event_ratio(window:pd.DataFrame)->float:
    return (window[window['k']=='bulk'].shape[0]/len(window))
def calculate_mean_cursor_jump(window:pd.DataFrame)->float:
    return (window['o'].diff().abs().mean())
def calculate_event_entropy(window:pd.DataFrame)->float:
    probs=window['k'].value_counts(normalize=True)
    entropy=-np.sum(probs*np.log2(probs))
    return entropy

def extract_features(window: pd.DataFrame)-> Dict[str, Any]:
    """
    Extract all 9 features for a single window.
    Args:
        window: DataFrame containing one window of events
    Returns:
        Dictionary of feature names and values
    """
    features = {
        'mean_dwell_time': calculate_mean_dwell_time(window),
        'flight_time_jitter': calcultate_std_flight_time(window),
        'typing_velocity': calculate_typing_velocity(window),
        'correction_rate': calculate_correction_rate(window),
        'burst_ratio': calculate_burst_ratio(window),
        'max_burst_length':calculate_max_burst_length(window),
        'bulk_event_ratio':calculate_bulk_event_ratio(window),
        'mean_cursor_jump':calculate_mean_cursor_jump(window),
        'event_entropy':calculate_event_entropy(window)
        
    }
    return features



