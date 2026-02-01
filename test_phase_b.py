#!/usr/bin/env python3
"""Quick test of Phase B implementation for v8 roadmap."""

from src.sat_mon.data.timeseries import (
    fetch_timeseries,
    extract_field_values,
    compute_ndvi_for_scene,
    fetch_ndvi_timeseries,
    SceneResult,
    TimeseriesPoint
)
import numpy as np
from datetime import datetime

print("Testing Phase B: Historical Data Fetching")
print("=" * 50)

# Test 1: SceneResult and TimeseriesPoint named tuples
scene = SceneResult(date=datetime.now(), item={'id': 'test'})
point = TimeseriesPoint(date=datetime.now(), value=0.65, metadata={'std': 0.1})
print("✅ Named tuples created successfully")
print(f"   SceneResult fields: {scene._fields}")
print(f"   TimeseriesPoint fields: {point._fields}")

# Test 2: Check module imports work
from src.sat_mon.data.timeseries import (
    fetch_multi_index_timeseries,
    fetch_lst_timeseries,
    fetch_rainfall_timeseries
)
print("✅ All timeseries functions imported")

# Test 3: Verify integration with field_boundary module
from src.sat_mon.analysis.field_boundary import create_circular_boundary, create_field_mask
boundary = create_circular_boundary(-28.736, 29.365, 250)
print("✅ Field boundary integration works")
print(f"   Created boundary for {boundary['properties']['area_ha']:.2f} ha field")

# Test 4: Run unit tests
import subprocess
result = subprocess.run(['python3', '-m', 'pytest', 'test_timeseries.py', '-v', '--tb=short'], 
                       capture_output=True, text=True)
passed = result.returncode == 0
test_count = result.stdout.count(' passed')
print(f"✅ Unit tests: {test_count} tests passed" if passed else f"❌ Unit tests failed")

print()
print("=" * 50)
print("Phase B: PASS ✅" if passed else "Phase B: FAIL ❌")
print("=" * 50)
