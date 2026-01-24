import numpy as np
from .thermal import compute_lst_baseline
from .radar import compute_flood_mask
from .weather import process_rainfall_accumulation

def process_indices(data):
    """Processes raw satellite data into visualization-ready indices."""
    processed = {}
    
    # Helper for safe division
    def safe_div(a, b):
        return np.divide(a, b, out=np.zeros_like(a), where=b!=0)
    
    # Process Sentinel-2 Indices
    if data.get("s2"):
        s2 = data["s2"]
        
        # 1. RGB
        def norm(b):
            return np.clip(b / 3000, 0, 1)
        processed["rgb"] = np.dstack([norm(s2["red"]), norm(s2["green"]), norm(s2["blue"])])

        # 2. NDVI: (NIR - Red) / (NIR + Red)
        processed["ndvi"] = safe_div((s2["nir"] - s2["red"]), (s2["nir"] + s2["red"]))

        # 3. NDRE: (NIR - RedEdge) / (NIR + RedEdge)
        processed["ndre"] = safe_div((s2["nir"] - s2["red_edge"]), (s2["nir"] + s2["red_edge"]))

        # 4. Cloud Mask (SCL)
        # SCL: 3=Shadow, 8=Medium, 9=High, 10=Cirrus
        cloud_mask = np.isin(s2["scl"], [3, 8, 9, 10])
        processed["cloud_mask"] = cloud_mask
    
    # Phase 2: Process Landsat LST with Anomaly Computation
    if data.get("landsat"):
        st_dn = data["landsat"]["st"]
        # USGS Collection 2 ST scaling: Kelvin = DN * 0.00341802 + 149.0
        # Celsius = Kelvin - 273.15
        lst_celsius = (st_dn * 0.00341802 + 149.0) - 273.15
        processed["lst"] = lst_celsius
        
        # Phase 2: Compute LST Anomaly
        bbox = data.get("bbox")
        if bbox:
            # Use current LST shape as reference
            lst_shape = lst_celsius.shape
            lst_baseline = compute_lst_baseline(bbox, lst_shape)
            if lst_baseline is not None and lst_baseline.shape == lst_celsius.shape:
                lst_anomaly = lst_celsius - lst_baseline
                processed["lst_anomaly"] = lst_anomaly
                mean_anomaly = np.nanmean(lst_anomaly)
                print(f"  LST anomaly: Mean={mean_anomaly:+.1f}°C")

    # Phase 2: Process Sentinel-1 Flood Detection
    if data.get("s1"):
        s1 = data["s1"]
        # Convert to dB: 10 * log10(x). Avoid log(0).
        def to_db(x):
            return 10 * np.log10(np.clip(x, 1e-5, None))
        
        processed["s1_vv_db"] = to_db(s1["vv"])
        processed["s1_vh_db"] = to_db(s1["vh"])
        
        # Phase 2: Compute flood mask and risk
        flood_mask, flood_risk = compute_flood_mask(s1["vv"], s1["vh"])
        processed["flood_mask"] = flood_mask
        processed["flood_risk"] = flood_risk
        flood_coverage = np.mean(flood_mask) * 100
        print(f"  Flood detection: {flood_coverage:.1f}% coverage")

    # Phase 2: Process Rainfall Accumulation
    if data.get("rain"):
        rain_processed = process_rainfall_accumulation(data["rain"])
        if rain_processed:
            processed.update(rain_processed)

    # Process Soil Moisture (WaPOR)
    if data.get("soil_moisture"):
        # WaPOR values are often scaled (e.g. 0-1000 for 0-100%)
        # Debugging showed range 500-1000, confirming 0.1 scale factor needed
        processed["soil_moisture"] = data["soil_moisture"]["relative"] * 0.1

    # Process Crop Mask
    if data.get("crop_mask") is not None:
        lc_data = data["crop_mask"]["classification"]
        # 40 = Cropland
        crop_mask = np.where(lc_data == 40, 1, 0).astype("float32")
        # Mask out 0s for transparency
        processed["crop_mask_plot"] = np.where(crop_mask == 1, 1, np.nan)
    else:
        processed["crop_mask_plot"] = None
        
    return processed
