import numpy as np

def process_rainfall_accumulation(rain_data):
    """
    Extracts and validates 7-day and 30-day rainfall accumulation.
    
    Phase 2: Rainfall Accumulation Processing
    """
    if rain_data is None:
        return None
    
    results = {}
    
    # Daily rain
    if "daily" in rain_data:
        results["daily"] = rain_data["daily"]
    
    # 7-day accumulation
    if "rain_7d" in rain_data:
        rain_7d = rain_data["rain_7d"]
        results["rain_7d"] = rain_7d
        mean_7d = np.nanmean(rain_7d)
        print(f"  7-day rainfall: Mean={mean_7d:.1f}mm")
    
    # 30-day accumulation
    if "rain_30d" in rain_data:
        rain_30d = rain_data["rain_30d"]
        results["rain_30d"] = rain_30d
        mean_30d = np.nanmean(rain_30d)
        print(f"  30-day rainfall: Mean={mean_30d:.1f}mm")
    
    return results if results else None
