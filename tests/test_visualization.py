import numpy as np
import matplotlib
matplotlib.use('Agg') # Prevent UI window
import matplotlib.pyplot as plt
from src.sat_mon.visualization.plots import plot_grid, CropMonitorVisualizer, plot_field_timeseries, plot_season_comparison

def test_get_extent_logic():
    print("\nTesting get_extent() logic...")
    
    # 1. Valid EPSG
    raw_data_valid = {
        "bbox": [28.0, -26.0, 28.1, -25.9],
        "s2": {"epsg": 32735}
    }
    viz = CropMonitorVisualizer({}, raw_data_valid)
    extent, crs = viz.get_extent()
    if crs == "EPSG:32735" and extent is not None:
        print("✓ Valid EPSG handled correctly")
    else:
        print(f"✗ Valid EPSG failed: {crs}, {extent}")

    # 2. Missing EPSG (Fallback)
    raw_data_missing = {
        "bbox": [28.0, -26.0, 28.1, -25.9],
        "s2": {} 
    }
    viz = CropMonitorVisualizer({}, raw_data_missing)
    extent, crs = viz.get_extent()
    if crs == "EPSG:3857" and extent is not None:
        print("✓ Missing EPSG fallback handled correctly")
    else:
        print(f"✗ Missing EPSG fallback failed: {crs}, {extent}")

    # 3. String EPSG (Coercion)
    raw_data_string = {
        "bbox": [28.0, -26.0, 28.1, -25.9],
        "s2": {"epsg": "32735"}
    }
    viz = CropMonitorVisualizer({}, raw_data_string)
    extent, crs = viz.get_extent()
    if crs == "EPSG:32735" and extent is not None:
        print("✓ String EPSG coercion handled correctly")
    else:
        print(f"✗ String EPSG coercion failed: {crs}, {extent}")

def test_visualization():
    print("Testing Visualization Grid (5x3)...")
    
    # Create mock processed data
    shape = (100, 100)
    processed = {
        "rgb": np.random.rand(100, 100, 3),
        "ndvi": np.random.rand(100, 100),
        "evi": np.random.rand(100, 100),
        "savi": np.random.rand(100, 100),
        "ndmi": np.random.rand(100, 100),
        "ndwi": np.random.rand(100, 100),
        "rvi": np.random.rand(100, 100),
        "crop_mask_plot": np.random.randint(0, 2, (100, 100)),
        "lst": np.random.rand(100, 100) * 30 + 10,
        "lst_anomaly": np.random.rand(100, 100) * 10 - 5,
        "soil_moisture": np.random.rand(100, 100) * 100,
        "flood_mask": np.random.rand(100, 100),
        "rain_7d": np.random.rand(100, 100) * 50,
        "rain_30d": np.random.rand(100, 100) * 150,
        "weather": {
            "dates": ["2026-01-24", "2026-01-25", "2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29", "2026-01-30"],
            "temp_max": [25, 26, 24, 23, 25, 27, 28],
            "temp_min": [15, 16, 14, 13, 15, 17, 18],
            "precip": [0, 5, 10, 0, 0, 0, 2]
        }
    }
    
    # Mock raw data for metadata dates
    raw_data = {
        "s2": {"metadata": {"properties": {"datetime": "2026-01-24T10:00:00Z"}}},
        "landsat": {"metadata": {"properties": {"datetime": "2026-01-23T10:00:00Z"}}},
        "s1": {"metadata": {"properties": {"datetime": "2026-01-24T05:00:00Z"}}},
        "rain": {"metadata": {"properties": {"datetime": "2026-01-24T00:00:00Z"}}},
        "crop_mask": {"metadata": {"properties": {"datetime": "2025-01-01T00:00:00Z"}}},
        "soil_moisture": {"metadata": {"properties": {"start_datetime": "2026-01-01T00:00:00Z"}}}
    }
    
    try:
        plot_grid(processed, raw_data)
        print("✓ Visualization generated successfully (no errors).")
        plt.close('all')
    except Exception as e:
        import traceback
        print(f"✗ Visualization failed: {e}")
        traceback.print_exc()

def test_plot_field_timeseries():
    print("\nTesting plot_field_timeseries()...")
    from src.sat_mon.visualization.plots import plot_field_timeseries
    from src.sat_mon.analysis.phenology import Season
    from datetime import datetime, timedelta

    dates = [datetime(2023, 1, 1) + timedelta(days=i*5) for i in range(20)]
    ndvi = [0.1 + 0.05*i for i in range(20)]
    
    # Test minimal args
    fig = plot_field_timeseries(dates, ndvi)
    if fig and len(fig.axes) == 1:
        print("✓ Minimal plot created")
    else:
        print("✗ Minimal plot failed")
    plt.close(fig)
    
    # Test all panels
    sm = [20.0] * 20
    lst = [300.0] * 20
    rain = [5.0] * 20
    
    fig = plot_field_timeseries(dates, ndvi, sm=sm, lst=lst, rainfall=rain)
    if fig and len(fig.axes) >= 4: # Can be 5 due to twinx
        print("✓ Multi-panel plot created")
    else:
        print(f"✗ Multi-panel plot failed (axes={len(fig.axes)})")
    plt.close(fig)

def test_plot_season_comparison():
    print("\nTesting plot_season_comparison()...")
    from src.sat_mon.visualization.plots import plot_season_comparison
    from src.sat_mon.analysis.phenology import Season
    from datetime import datetime
    
    seasons = [
        Season(datetime(2023,1,1), datetime(2023,3,1), 0.8, datetime(2023,5,1), 120, "excellent"),
        Season(datetime(2024,1,1), datetime(2024,3,1), 0.5, datetime(2024,5,1), 120, "moderate")
    ]
    
    fig = plot_season_comparison(seasons)
    if fig and len(fig.axes) >= 2: # Bar + Duration line
        print("✓ Comparison chart created")
    else:
        print("✗ Comparison chart failed")
    plt.close(fig)

if __name__ == "__main__":
    test_get_extent_logic()
    test_visualization()
    test_plot_field_timeseries()
    test_plot_season_comparison()
    print("\nVisualization tests complete.")
