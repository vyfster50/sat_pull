
import numpy as np
import matplotlib
matplotlib.use('Agg') # Prevent UI window
import matplotlib.pyplot as plt
from src.sat_mon.visualization.plots import plot_grid

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

if __name__ == "__main__":
    test_visualization()
