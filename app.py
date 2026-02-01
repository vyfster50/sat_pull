#!/usr/bin/env python3
"""
Crop Monitoring App v4 - Main Application
=========================================
"""

import sys
import os

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from sat_mon.config import setup_environment
from sat_mon.data.composite import get_satellite_data
from sat_mon.processing.indices import process_indices
from sat_mon.analysis.alerts import analyze_thresholds
from sat_mon.visualization.reports import generate_report
from sat_mon.visualization.plots import plot_grid

def get_interactive_input():
    """Get location and resolution interactively from user."""
    print(f"\n{'='*50}")
    print("SATELLITE CROP MONITORING ANALYSIS")
    print(f"{'='*50}\n")
    
    # Default values
    default_lat = -28.736214289538538
    default_lon = 29.365144005056933
    default_buffer = 0.05
    
    # Get position
    print("Enter position as: lat, lon")
    print(f"Example: -28.734724030406774, 29.36506872445845")
    print(f"(Press Enter for default: {default_lat}, {default_lon})")
    position_input = input("\nPosition: ").strip()
    
    if position_input:
        try:
            parts = position_input.split(",")
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
        except (ValueError, IndexError):
            print("Invalid format. Using default position.")
            lat, lon = default_lat, default_lon
    else:
        lat, lon = default_lat, default_lon
    
    # Get resolution/buffer
    print("\nResolution (buffer size in degrees):")
    print("  1 = ~1.1 km  (high zoom, small area)")
    print("  2 = ~5.5 km  (medium area) [default]")
    print("  3 = ~11 km   (large area)")
    print("  4 = ~22 km   (very wide area)")
    print("  Or enter custom value (e.g., 0.03)")
    res_input = input("\nResolution [1-4 or custom]: ").strip()
    
    # Default to 0.03 (approximately 3km) if empty
    if not res_input:
        buffer = 0.03
    else:
        try:
            # Map 1-4 to buffer sizes
            res_mapping = {
                "1": 0.01,
                "2": 0.05,
                "3": 0.1,
                "4": 0.2
            }
            buffer = res_mapping.get(res_input, float(res_input))
        except ValueError:
            print("Invalid resolution. Using default (0.05).")
            buffer = 0.05
    
    print(f"Selected coordinates: ({lat}, {lon})")
    print(f"Selected resolution: {buffer}° (approx. {buffer * 111320:.0f} meters)")
    if buffer >= 0.2:
        print("[warning] Large area selected. Imagery will be downsampled to prevent out-of-memory.")
    
    return lat, lon, buffer

def main():
    setup_environment()
    
    # Interactive input
    lat, lon, buffer = get_interactive_input()
    
    # Display configuration
    print(f"\n{'='*50}")
    print(f"CONFIGURATION")
    print(f"{'='*50}")
    print(f"Location: {lat}, {lon}")
    print(f"Resolution: {buffer}° (~{buffer * 111:.1f} km radius)")
    print(f"Mode: Fetching latest available data from all sources")
    print(f"{'='*50}\n")
    
    # 1. Data Acquisition
    print("Fetching data...")
    raw_data = get_satellite_data(
        lat=lat,
        lon=lon,
        buffer=buffer
    )
    
    # 2. Processing
    print("Processing indices...")
    processed_data = process_indices(raw_data)
    
    # 3. Analysis
    analysis_results = analyze_thresholds(processed_data)
    
    # 4. Output
    print("Generating response...")
    generate_report(processed_data, analysis_results, raw_data=raw_data)
    plot_grid(processed_data, raw_data=raw_data)

if __name__ == "__main__":
    main()
