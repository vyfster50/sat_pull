#!/usr/bin/env python3
"""
Crop Monitoring App v4 - Main Application
=========================================
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from sat_mon.config import setup_environment
from sat_mon.data.composite import get_satellite_data
from sat_mon.processing.indices import process_indices
from sat_mon.analysis.alerts import analyze_thresholds
from sat_mon.visualization.reports import generate_report, generate_historical_report
from sat_mon.visualization.plots import plot_grid, plot_field_timeseries
from sat_mon.data.timeseries import (
    fetch_ndvi_timeseries, 
    fetch_lst_timeseries, 
    fetch_rainfall_timeseries
)
from sat_mon.analysis.phenology import detect_seasons

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

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Satellite Crop Monitoring')
    parser.add_argument('--historical', action='store_true', 
                        help='Run historical field-level analysis')
    parser.add_argument('--lat', type=float, help='Field center latitude')
    parser.add_argument('--lon', type=float, help='Field center longitude')
    parser.add_argument('--radius', type=float, default=500.0, 
                        help='Field radius in meters (for circular)')
    parser.add_argument('--start', type=str, 
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, 
                        help='End date (YYYY-MM-DD)')
    return parser.parse_args()

def get_historical_input():
    """Get field definition and date range for historical analysis."""
    print(f"\n{'='*50}")
    print("HISTORICAL FIELD ANALYSIS")
    print(f"{'='*50}\n")
    
    # Default values
    default_lat = -28.736214289538538
    default_lon = 29.365144005056933
    default_radius = 500
    default_end = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=365*3)).strftime("%Y-%m-%d")

    # Get position
    print("Enter field center as: lat, lon")
    print(f"Example: -28.7347, 29.3650")
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
        
    # Get Field Type - Placeholder for future polygon support
    print("\nField type:")
    print("  1 = Circular (pivot irrigation)")
    print("  2 = Polygon (irregular field) [Not fully supported yet]")
    ftype = input("Field type [1]: ").strip()
    
    # Get Dimensions
    if ftype == '2':
        print("Using circular approximation for now.")
        
    print(f"\nRadius in meters (default {default_radius}):")
    rad_input = input(f"Radius [{default_radius}]: ").strip()
    radius = float(rad_input) if rad_input else float(default_radius)
    
    # Get Date Range
    print(f"\nDate range:")
    start_input = input(f"Start date [{default_start}]: ").strip()
    start_date = start_input if start_input else default_start
    
    end_input = input(f"End date [{default_end}]: ").strip()
    end_date = end_input if end_input else default_end
    
    return lat, lon, radius, start_date, end_date

def run_historical_analysis(lat, lon, radius, start_date, end_date):
    """Execute full historical pipeline."""
    print(f"\nRunning historical analysis for {start_date} to {end_date}...")
    print(f"Field: {lat}, {lon} (Radius: {radius}m)")
    
    # 1. Fetch NDVI timeseries
    print("\nFetching Sentinel-2 NDVI data...")
    try:
        ndvi_result = fetch_ndvi_timeseries(lat, lon, radius_m=radius, start_date=start_date, end_date=end_date)
        ndvi_dates = ndvi_result['dates']
        ndvi_values = ndvi_result['ndvi']
        print(f"  -> Retrieved {len(ndvi_values)} data points.")
    except Exception as e:
        print(f"  -> Error fetching NDVI: {e}")
        return

    # 2. Fetch LST timeseries
    print("Fetching Landsat LST data...")
    lst_dates, lst_values = [], []
    try:
        lst_result = fetch_lst_timeseries(lat, lon, radius_m=radius, start_date=start_date, end_date=end_date)
        lst_dates = lst_result['dates']
        lst_values = lst_result['lst']
        print(f"  -> Retrieved {len(lst_values)} data points.")
    except Exception as e:
        print(f"  -> Warning: Could not fetch LST data ({e}). Continuing.")

    # 3. Fetch rainfall timeseries
    print("Fetching CHIRPS Rainfall data...")
    rain_dates, rain_values = [], []
    try:
        rain_result = fetch_rainfall_timeseries(lat, lon, radius_m=radius, start_date=start_date, end_date=end_date)
        rain_dates = rain_result['dates']
        rain_values = rain_result['rainfall']
        print(f"  -> Retrieved {len(rain_values)} data points.")
    except Exception as e:
        print(f"  -> Warning: Could not fetch rainfall data ({e}). Continuing.")
        
    # 4. Detect seasons
    print("Detecting crop seasons...")
    seasons = detect_seasons(ndvi_dates, ndvi_values)
    print(f"  -> Detected {len(seasons)} seasons.")
    
    # 5. Generate Report
    # Prepare stats
    ndvi_stats = {
        'count': len(ndvi_values),
        'mean': sum(x for x in ndvi_values if x is not None) / len([x for x in ndvi_values if x is not None]) if ndvi_values else 0
    }
    lst_stats = {
        'count': len(lst_values)
    }
    rain_clean = [x for x in rain_values if x is not None]
    rain_stats = {
        'days': len(rain_values),
        'total_mm': sum(rain_clean) if rain_clean else 0
    }
    
    # Convert Season named tuples to dicts for the report function
    season_dicts = []
    for s in seasons:
        season_dicts.append({
            'season_type': 'Season', 
            'planting_date': s.start_date.strftime('%Y-%m-%d'),
            'harvest_date': s.end_date.strftime('%Y-%m-%d'),
            'duration_days': s.duration_days,
            'peak_ndvi': s.peak_ndvi,
            'health_rating': s.health
        })
        
    generate_historical_report(season_dicts, ndvi_stats, lst_stats, rain_stats)
    
    # 6. Generate Plots
    print("Generating visualizations...")
    # Note: plot_field_timeseries requires all arrays to match dates length
    # For now, only pass NDVI (primary series) and skip optional series if mismatched
    plot_field_timeseries(
        dates=ndvi_dates, 
        ndvi=ndvi_values,
        sm=None,  # Soil moisture not fetched yet
        lst=lst_values if len(lst_values) == len(ndvi_values) else None,
        rainfall=rain_values if len(rain_values) == len(ndvi_values) else None,
        seasons=seasons,
        field_name=f"Field Analysis: {lat}, {lon}"
    )
    
    # Force display of the plot
    import matplotlib.pyplot as plt
    plt.show()
    
    print("Done.")

def main():
    setup_environment()
    args = parse_arguments()
    
    # Check for historical analysis mode
    if args.historical:
        if args.lat and args.lon:
             # Non-interactive mode
             lat, lon = args.lat, args.lon
             radius = args.radius
             start = args.start if args.start else '2023-01-01'
             end = args.end if args.end else datetime.now().strftime('%Y-%m-%d')
        else:
             # Interactive historical mode
             lat, lon, radius, start, end = get_historical_input()
        
        run_historical_analysis(lat, lon, radius, start, end)
        return
    
    # Original Interactive input
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
