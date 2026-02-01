import pytest
import numpy as np
from datetime import datetime, timedelta
from src.sat_mon.analysis.phenology import (
    smooth_timeseries,
    detect_seasons,
    classify_health,
    Season
)

# Helper to generate dates
def generate_dates(start_str, count, interval_days=5):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    return [start + timedelta(days=i*interval_days) for i in range(count)]

def test_smooth_timeseries_basic():
    """Test basic smoothing functionality."""
    # Step function: 0, 0, 1, 1, 0, 0
    values = [0.1, 0.1, 0.8, 0.8, 0.1, 0.1]
    smoothed = smooth_timeseries(values, window=3)
    
    assert len(smoothed) == len(values)
    # Check max is dampened (max of avg(0.1, 0.8, 0.8) = 0.56)
    assert np.max(smoothed) < 0.8 
    
def test_smooth_timeseries_nan():
    """Test NaN interpolation."""
    values = [0.1, 0.2, None, 0.4, 0.5]
    smoothed = smooth_timeseries(values, window=3)
    
    # None should be interpolated to 0.3
    # Then smoothed.
    assert not np.any(np.isnan(smoothed))
    assert len(smoothed) == 5
    # Value at index 2 (was None) should be roughly 0.3 (linear interp)
    # Then smoothed with neighbors.

def test_detect_seasons_single():
    """Test detection of a single season."""
    dates = generate_dates("2023-01-01", 70) # 350 days
    # Create a bell curve signal
    x = np.linspace(-3, 3, 70)
    ndvi = 0.1 + 0.7 * np.exp(-x**2) # Peak 0.8, base 0.1
    
    seasons = detect_seasons(dates, ndvi.tolist(), threshold=0.25)
    
    assert len(seasons) == 1
    s = seasons[0]
    assert 0.7 < s.peak_ndvi < 0.9
    assert s.duration_days > 50
    assert s.health in ['good', 'excellent']

def test_detect_seasons_multi():
    """Test detection of multiple seasons."""
    dates = generate_dates("2023-01-01", 100)
    # Two peaks
    x = np.linspace(0, 4*np.pi, 100)
    ndvi = 0.1 + 0.35 * (np.sin(x - np.pi/2) + 1) # Range 0.1 to 0.8
    
    # 0.1 + 0.35(0) = 0.1 (min)
    # 0.1 + 0.35(2) = 0.8 (max)
    # Sin wave starts at -1 (0.1), goes up.
    
    seasons = detect_seasons(dates, ndvi.tolist(), threshold=0.3)
    
    # Should detect 2 seasons
    assert len(seasons) == 2

def test_classify_health():
    """Test health classification logic."""
    # Excellent
    s1 = Season(datetime.now(), datetime.now(), 0.75, datetime.now(), 160, "")
    assert classify_health(s1) == "excellent"
    
    # Good
    s2 = Season(datetime.now(), datetime.now(), 0.65, datetime.now(), 130, "")
    assert classify_health(s2) == "good"
    
    # Moderate
    s3 = Season(datetime.now(), datetime.now(), 0.5, datetime.now(), 100, "")
    assert classify_health(s3) == "moderate"
    
    # Poor
    s4 = Season(datetime.now(), datetime.now(), 0.3, datetime.now(), 50, "")
    assert classify_health(s4) == "poor"

def test_short_input():
    """Test behavior with input shorter than window."""
    dates = generate_dates("2023-01-01", 3)
    ndvi = [0.1, 0.2, 0.1]
    seasons = detect_seasons(dates, ndvi)
    assert len(seasons) == 0
