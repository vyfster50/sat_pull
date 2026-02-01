#!/usr/bin/env python3
"""Quick test of Phase C implementation for v8 roadmap."""

from src.sat_mon.analysis.phenology import (
    smooth_timeseries,
    detect_seasons,
    classify_health,
    Season
)
from datetime import datetime, timedelta
import numpy as np

print("Testing Phase C: Phenology Detection")
print("=" * 50)

# 1. Generate synthetic NDVI data
print("\n1. Generating synthetic data (3 years)...")
start_date = datetime(2023, 1, 1)
dates = [start_date + timedelta(days=5*i) for i in range(220)] # ~3 years
# Create seasonality: 3 full cycles
x = np.linspace(0, 6*np.pi, 220)
# Signal: base 0.15 + Seasonality + Noise
# sin goes -1 to 1. (sin+1)/2 goes 0 to 1.
# 0.15 + 0.6*... -> 0.15 to 0.75 range
ndvi = 0.15 + 0.6 * (np.sin(x - np.pi/2) + 1)/2 + np.random.normal(0, 0.02, 220)

# Add some clouds (drops to low values)
mask = np.random.choice([False, True], size=220, p=[0.9, 0.1])
ndvi[mask] = 0.05

# 2. Smooth
print("2. Smoothing time series...")
smoothed = smooth_timeseries(ndvi.tolist(), window=5)
print(f"   Original len: {len(ndvi)}, Smoothed len: {len(smoothed)}")
print(f"   Sample smoothed values: {smoothed[100:105]}")

# 3. Detect
print("3. Detecting seasons...")
seasons = detect_seasons(dates, ndvi.tolist(), threshold=0.3)

print(f"   Found {len(seasons)} seasons:")
for i, s in enumerate(seasons):
    print(f"   Season {i+1}:")
    print(f"     Start: {s.start_date.strftime('%Y-%m-%d')}")
    print(f"     Peak:  {s.peak_date.strftime('%Y-%m-%d')} (NDVI: {s.peak_ndvi:.2f})")
    print(f"     End:   {s.end_date.strftime('%Y-%m-%d')}")
    print(f"     Dur:   {s.duration_days} days")
    print(f"     Health: {s.health}")

print("\nPhase C Test Complete.")
