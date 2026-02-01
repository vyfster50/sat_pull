"""
Phenology Detection Module for Satellite Crop Monitoring.

This module provides functions to analyze NDVI time series to detect
growing seasons (planting to harvest) and assess crop health.

Phase C Implementation - Phenology Detection
"""

import numpy as np
from typing import List, NamedTuple, Optional
from datetime import datetime, timedelta

# Data structure for detected seasons
class Season(NamedTuple):
    start_date: datetime
    peak_date: datetime
    peak_ndvi: float
    end_date: datetime
    duration_days: int
    health: str

def smooth_timeseries(values: List[Optional[float]], window: int = 5) -> np.ndarray:
    """
    Apply smoothing to reduce noise from cloud artifacts.
    Interpolates NaNs before applying rolling mean.
    
    Args:
        values: List of NDVI values (can contain None/NaN).
        window: Window size for rolling mean. Defaults to 5.
        
    Returns:
        Smoothed numpy array.
    """
    if not values:
        return np.array([])
        
    # Convert to float array, treating None as NaN
    arr = np.array(values, dtype=float)
    
    # Interpolate NaNs
    nans = np.isnan(arr)
    if np.all(nans):
        return arr # All NaNs
        
    if np.any(nans):
        x = np.arange(len(arr))
        arr[nans] = np.interp(x[nans], x[~nans], arr[~nans])
        
    if len(arr) < window:
        return arr
        
    # Handle edges by padding with edge values
    pad_width = window // 2
    # Ensure window is odd for symmetric padding, or handle generic
    # If window is even, we might need asymmetric padding or just accept slight shift
    # For now assuming odd window or close enough
    
    padded = np.pad(arr, pad_width, mode='edge')
    
    # Correction for even windows if necessary, but standard is odd
    if window % 2 == 0:
        # If even, pad one less on right or handle valid output size
        # valid output size = N + 2*pad - K + 1
        # if N=10, K=4, pad=2. N_pad=14. Out=11. Too long.
        # Just use odd windows logic or slice.
        padded = padded[:-1] 
        
    kernel = np.ones(window) / window
    smoothed = np.convolve(padded, kernel, mode='valid')
    
    return smoothed

def detect_seasons(
    dates: List[datetime], 
    ndvi_values: List[float], 
    threshold: float = 0.25,
    sharp_drop: float = 0.2,
    sharp_drop_days: int = 14,
    min_duration: int = 30,
    close_unclosed: bool = True
) -> List[Season]:
    """
    Detect growing seasons from NDVI time series.
    
    Args:
        dates: List of dates sorted chronologically.
        ndvi_values: Corresponding NDVI values.
        threshold: NDVI threshold for season start/end.
        sharp_drop: NDVI decrease to trigger harvest detection.
        sharp_drop_days: Time window for sharp drop (days).
        min_duration: Minimum season duration to filter noise.
        close_unclosed: If True, close any open season at end of data.
        
    Returns:
        List of Season objects.
    """
    if not dates or not ndvi_values or len(dates) != len(ndvi_values):
        return []
        
    # Smooth the data
    smoothed_ndvi = smooth_timeseries(ndvi_values)
    
    seasons = []
    in_season = False
    season_start_idx = -1
    
    def _create_season(start_idx: int, end_idx: int) -> Optional[Season]:
        """Helper to create a Season from indices."""
        season_slice = smoothed_ndvi[start_idx:end_idx+1]
        peak_val = np.max(season_slice)
        peak_idx_rel = np.argmax(season_slice)
        peak_idx_abs = start_idx + peak_idx_rel
        
        start_date = dates[start_idx]
        end_date = dates[end_idx]
        peak_date = dates[peak_idx_abs]
        
        duration = (end_date - start_date).days
        
        # Filter out very short seasons (noise)
        if duration < min_duration:
            return None

        season = Season(
            start_date=start_date,
            peak_date=peak_date,
            peak_ndvi=float(peak_val),
            end_date=end_date,
            duration_days=duration,
            health="pending" 
        )
        
        health_status = classify_health(season)
        return season._replace(health=health_status)
    
    for i in range(1, len(smoothed_ndvi)):
        val = smoothed_ndvi[i]
        prev_val = smoothed_ndvi[i-1]
        
        # Detect Start: crossing threshold upwards
        if not in_season and val >= threshold and prev_val < threshold:
            in_season = True
            season_start_idx = i
            
        # Detect End: crossing threshold downwards OR sharp drop
        elif in_season:
            is_end = False
            
            # Threshold crossing check
            if val < threshold:
                is_end = True
            
            # Sharp drop detection (harvest indicator)
            # Look back up to sharp_drop_days
            if not is_end and i >= 2:
                days_back = (dates[i] - dates[i-1]).days
                lookback = 1
                while lookback < i - season_start_idx:
                    total_days = sum((dates[i-j] - dates[i-j-1]).days for j in range(lookback))
                    if total_days > sharp_drop_days:
                        break
                    lookback += 1
                
                if lookback > 0:
                    recent_max = np.max(smoothed_ndvi[i-lookback:i])
                    if recent_max - val >= sharp_drop:
                        is_end = True
            
            if is_end:
                in_season = False
                season = _create_season(season_start_idx, i)
                if season:
                    seasons.append(season)
    
    # Handle unclosed season at end of data
    if in_season and close_unclosed:
        season = _create_season(season_start_idx, len(smoothed_ndvi) - 1)
        if season:
            seasons.append(season)

    return seasons

def classify_health(season: Season) -> str:
    """
    Classifies season health based on peak NDVI and duration.
    
    Returns: 'excellent', 'good', 'moderate', 'poor'
    """
    peak = season.peak_ndvi
    duration = season.duration_days
    
    if peak > 0.7 and duration > 150:
        return 'excellent'
    elif peak > 0.6 and duration > 120:
        return 'good'
    elif peak > 0.4 and duration > 90:
        return 'moderate'
    else:
        return 'poor'
