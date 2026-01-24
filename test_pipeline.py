#!/usr/bin/env python3
"""Test script for Phase 2 pipeline debugging."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from sat_mon.config import setup_environment
from sat_mon.data.composite import get_satellite_data
from sat_mon.processing.indices import process_indices
from sat_mon.analysis.alerts import analyze_thresholds

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

setup_environment()

lat, lon, buffer = -28.736214289538538, 29.365144005056933, 0.05

print('=== FULL PIPELINE TEST ===')
print()

# 1. Data Acquisition
print('1. Data Acquisition...')
data = get_satellite_data(lat, lon, buffer)
print('   ✓ Complete')

# 2. Processing (includes Phase 2 functions)
print()
print('2. Processing Pipeline (Phase 2)...')
try:
    processed = process_indices(data)
    print(f'   Processed keys: {list(processed.keys())}')
    
    # Check Phase 2 outputs
    phase2_outputs = ['lst_anomaly', 'flood_mask', 'flood_risk', 'rain_7d', 'rain_30d', 
                      'evi', 'savi', 'ndmi', 'ndwi', 'rvi', 'weather']
    for key in phase2_outputs:
        if key in processed:
            if processed[key] is not None:
                # Handle boolean arrays (cloud_mask) or scalar values if any
                shape = getattr(processed[key], 'shape', 'scalar')
                print(f'   ✓ {key}: shape={shape}')
            else:
                print(f'   - {key}: None (Data missing)')
        else:
            print(f'   ✗ {key}: MISSING')
except Exception as e:
    import traceback
    print(f'   ERROR: {e}')
    traceback.print_exc()

# 3. Analysis
print()
print('3. Alert Analysis...')
try:
    analysis = analyze_thresholds(processed)
    print(f'   Stats: {analysis["stats"]}')
    print(f'   Alerts: {len(analysis["alerts"])} active')
    for alert in analysis['alerts']:
        print(f'   - [{alert["severity"]}] {alert["type"]}')
except Exception as e:
    import traceback
    print(f'   ERROR: {e}')
    traceback.print_exc()

print()
print('=== TEST COMPLETE ===')
