#!/usr/bin/env python3
"""Integration test for Phase D (Visualization)."""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
from src.sat_mon.analysis.phenology import detect_seasons, Season
from src.sat_mon.visualization.plots import plot_field_timeseries, plot_season_comparison

print("Testing Phase D: Visualization")
print("=" * 50)

# 1. Generate synthetic data (3 years)
print("\n1. Generating synthetic data...")
start_date = datetime(2023, 1, 1)
days = 1095 # 3 years
dates = [start_date + timedelta(days=i) for i in range(days)]

# Sparse dates for satellite (every 5 days)
sat_indices = list(range(0, days, 5))
sat_dates = [dates[i] for i in sat_indices]

# Synthetic NDVI: 3 seasons
x = np.linspace(0, 6*np.pi, len(sat_indices))
ndvi = 0.15 + 0.6 * (np.sin(x - np.pi/2) + 1)/2 + np.random.normal(0, 0.02, len(sat_indices))
ndvi_list = ndvi.tolist()

# Synthetic Soil Moisture (every 10 days)
sm_indices = list(range(0, days, 10))
sm_dates = [dates[i] for i in sm_indices] # Not used directly in aligned list, but conceptual
# Create aligned list with Nones
sm_aligned = [None] * len(sat_indices)
for i in range(0, len(sat_indices), 2): # Every 10 days roughly
    sm_aligned[i] = 0.1 + 0.3 * np.random.random()

# Synthetic LST (every 16 days)
lst_aligned = [None] * len(sat_indices)
for i in range(0, len(sat_indices), 3):
    lst_aligned[i] = 300 + 10 * np.sin(x[i]) + np.random.normal(0, 2) # Kelvin

# Synthetic Rainfall (Daily)
rainfall_daily = np.random.exponential(scale=2.0, size=len(sat_indices)).tolist() # Simplified to align with sat dates for plot function

# 2. Detect Seasons
print("2. Detecting seasons...")
seasons = detect_seasons(sat_dates, ndvi_list, threshold=0.3)
print(f"   Found {len(seasons)} seasons")

# 3. Test Time Series Plot
print("3. Generating time series plot...")
fig1 = plot_field_timeseries(
    dates=sat_dates,
    ndvi=ndvi_list,
    sm=sm_aligned,
    lst=lst_aligned,
    rainfall=rainfall_daily,
    seasons=seasons,
    field_name="Test Pivot Field",
    save_path="test_phase_d_timeseries.png"
)

# 4. Test Comparison Plot
print("4. Generating comparison plot...")
fig2 = plot_season_comparison(
    seasons=seasons,
    save_path="test_phase_d_comparison.png"
)

print("\nPhase D Test Complete. Check output PNG files.")
