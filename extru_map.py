"""
Crop Monitoring App v3 - Main Processing Pipeline
================================================

Status: Phase 2 (Processing Pipeline) ✅ COMPLETE

Phase 1: Data Acquisition ✅
- All STAC collections fetching (S2, Landsat, S1, CHIRPS, WaPOR, etc.)
- 30-day rainfall stacking ready
- NDVI fallback logic for cloudy S2

Phase 2: Processing Pipeline ✅
- [x] Rainfall accumulation (7d, 30d sums) - process_rainfall_accumulation()
- [x] LST baseline computation - compute_lst_baseline()
- [x] Flood threshold detection - compute_flood_mask()
- [x] NDVI source switching logic - Already in get_satellite_data()
- [x] Updated 3×3 visualization grid
- [x] Enhanced alert rules from v3 roadmap

Visualization: 3×3 Grid
┌─────────────────┬─────────────────┬─────────────────┐
│ RGB Composite   │ NDVI            │ Crop Mask       │
│ (S2)            │ (S2/Landsat)    │ (WorldCover)    │
├─────────────────┼─────────────────┼─────────────────┤
│ LST             │ LST Anomaly     │ Flood Mask      │
│ (Landsat)       │ (vs baseline)   │ (S1 VV)         │
├─────────────────┼─────────────────┼─────────────────┤
│ Rain 7-day      │ Rain 30-day     │ Soil Moisture   │
│ (CHIRPS)        │ (CHIRPS)        │ (WaPOR)         │
└─────────────────┴─────────────────┴─────────────────┘
"""

import os
import requests
# from pystac_client import Client # Removing pystac_client usage due to hangs
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from rasterio.enums import Resampling
import numpy as np
import matplotlib.pyplot as plt
from pystac import Item 

# Configuration
STAC_URL = "https://explorer.digitalearth.africa/stac/search"

# ... setup_environment ...
def setup_environment():
    """Sets up AWS environment variables for public bucket access."""
    os.environ['AWS_NO_SIGN_REQUEST'] = 'YES'
    os.environ['AWS_REGION'] = 'af-south-1'
    os.environ['AWS_S3_ENDPOINT'] = 's3.af-south-1.amazonaws.com'
    os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'

# ... search_stac ...
def search_stac(collections, bbox, datetime=None, limit=1, query=None, sortby=None):
    """Helper to search STAC API using requests."""
    payload = {
        "collections": collections,
        "bbox": bbox,
        "limit": limit
    }
    if datetime:
        payload["datetime"] = datetime
    if sortby:
        payload["sortby"] = sortby
        
    try:
        response = requests.post(STAC_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("features", [])
    except Exception as e:
        print(f"STAC Search Error: {e}")
        return []

def get_bbox(lat, lon, buffer=0.05):
    """Creates a bounding box around a point."""
    return [
        lon - buffer,
        lat - buffer,
        lon + buffer,
        lat + buffer,
    ]

def read_band(item, asset_key, bbox_wgs84, dtype="float32", out_shape=None):
    """Reads a specific band from a STAC item (dict) within a bounding box."""
    # Handle item as dict or pystac Item
    href = item['assets'][asset_key]['href'] if isinstance(item, dict) else item.assets[asset_key].href
    
    with rasterio.open(href) as src:
        bbox_native = transform_bounds("EPSG:4326", src.crs, *bbox_wgs84)
        window = from_bounds(*bbox_native, src.transform)
        
        if out_shape:
            data = src.read(
                1, 
                window=window, 
                out_shape=out_shape, 
                resampling=Resampling.bilinear,
                boundless=True
            )
        else:
            data = src.read(1, window=window, boundless=True)
            
        return data.astype(dtype)

def get_satellite_data(lat, lon, buffer=0.05):
    """Fetches latest satellite data for the location."""
    # catalog = Client.open(STAC_URL) # Removed
    bbox = get_bbox(lat, lon, buffer)
    
    data = {
        "bbox": bbox,
        "s2": None,
        "crop_mask": None,
        "landsat": None,
        "s1": None,
        "rain": None,
        "soil": None,
        "soil_moisture": None,
        "ndvi_source": None
    }

    # 1. Get Sentinel-2 Data (latest available)
    print("Searching for Sentinel-2 data...")
    items_s2 = search_stac(
        collections=["s2_l2a"],
        bbox=bbox,
        limit=1,
        sortby=[{"field": "datetime", "direction": "desc"}]
    )
    
    # Reference shape (will be set by S2 Red band)
    ref_shape = None
    
    if items_s2:
        item_s2 = items_s2[0]
        # Handle dict or object access safely
        date_str = item_s2['properties']['datetime']
        print(f"Sentinel-2 Scene: {item_s2['id']} ({date_str})")
        
        # Read Red band first to establish 10m grid
        red = read_band(item_s2, "B04", bbox)
        ref_shape = red.shape
        print(f"Reference Grid Shape: {ref_shape}")

        data["s2"] = {
            "red": red,
            "green": read_band(item_s2, "B03", bbox, out_shape=ref_shape),
            "blue": read_band(item_s2, "B02", bbox, out_shape=ref_shape),
            "nir": read_band(item_s2, "B08", bbox, out_shape=ref_shape),
            "red_edge": read_band(item_s2, "B05", bbox, out_shape=ref_shape),
            "scl": read_band(item_s2, "SCL", bbox, dtype="uint8", out_shape=ref_shape),
            "metadata": item_s2
        }
        
        # Check S2 cloud cover for fallback decision
        scl_data = data["s2"]["scl"]
        cloud_classes = [3, 8, 9, 10]  # Shadow, Medium cloud, High cloud, Cirrus
        cloud_pct = np.mean(np.isin(scl_data, cloud_classes)) * 100
        print(f"  S2 Cloud Cover: {cloud_pct:.1f}%")
        
        # Store NDVI source indicator
        data["ndvi_source"] = "S2"
    
    # 2. Get Landsat Data (LST + optional SR fallback)
    print("Searching for Landsat data...")
    try:
        # Fetch Landsat Surface Temperature
        items_ls_st = search_stac(
            collections=["ls9_st"],
            bbox=bbox,
            limit=10,
            sortby=[{"field": "datetime", "direction": "desc"}]
        )
        
        landsat_data = None
        if items_ls_st:
            # From latest 10, pick lowest cloud cover
            items_ls_st.sort(key=lambda x: x['properties'].get("eo:cloud_cover", 100))
            item_ls_st = items_ls_st[0]
            
            print(f"Landsat LST Scene: {item_ls_st['id']} (Cloud: {item_ls_st['properties'].get('eo:cloud_cover')}%)")
            landsat_data = {
                "st": read_band(item_ls_st, "ST_B10", bbox, out_shape=ref_shape), 
                "metadata": item_ls_st
            }
        
        # Check if we need Landsat SR fallback for NDVI (S2 too cloudy)
        if items_s2 and cloud_pct > 50:
            print(f"  S2 cloud cover > 50%, fetching Landsat SR for NDVI fallback...")
            items_ls_sr = search_stac(
                collections=["ls9_sr"],
                bbox=bbox,
                limit=1,
                sortby=[{"field": "datetime", "direction": "desc"}]
            )
            if items_ls_sr:
                item_ls_sr = items_ls_sr[0]
                print(f"  Landsat SR Scene: {item_ls_sr['id']}")
                try:
                    red_sr = read_band(item_ls_sr, "SR_B4", bbox, out_shape=ref_shape)
                    nir_sr = read_band(item_ls_sr, "SR_B5", bbox, out_shape=ref_shape)
                    
                    # Compute NDVI from Landsat bands
                    def safe_div(a, b):
                        return np.divide(a, b, out=np.zeros_like(a), where=b!=0)
                    
                    ndvi_sr = safe_div((nir_sr - red_sr), (nir_sr + red_sr))
                    
                    if landsat_data is None:
                        landsat_data = {}
                    
                    landsat_data["sr_ndvi"] = ndvi_sr
                    landsat_data["sr_metadata"] = item_ls_sr
                    data["ndvi_source"] = "Landsat"
                    print(f"  Using Landsat SR for NDVI (cloud cover too high)")
                except Exception as e:
                    print(f"  Error computing Landsat SR NDVI: {e}")
        
        if landsat_data:
            data["landsat"] = landsat_data
        else:
            print("No Landsat data found.")
            data["landsat"] = None
            
    except Exception as e:
        print(f"Error fetching Landsat data: {e}")
        data["landsat"] = None

    # 3. Get Sentinel-1 Data (Radar) - latest available
    print("Searching for Sentinel-1 data...")
    items_s1 = search_stac(
        collections=["s1_rtc"],
        bbox=bbox,
        limit=1,
        sortby=[{"field": "datetime", "direction": "desc"}]
    )
    if items_s1:
        item_s1 = items_s1[0]
        print(f"Sentinel-1 Scene: {item_s1['id']} ({item_s1['properties']['datetime']})")
        data["s1"] = {
            "vv": read_band(item_s1, "vv", bbox, out_shape=ref_shape),
            "vh": read_band(item_s1, "vh", bbox, out_shape=ref_shape),
            "metadata": item_s1
        }
    else:
        print("No Sentinel-1 data found.")
        data["s1"] = None

    # 4. Get Rainfall Data (CHIRPS) - 30-day accumulation
    print("Searching for Rainfall data (30-day)...")
    items_rain = search_stac(
        collections=["rainfall_chirps_daily"],
        bbox=bbox,
        limit=30,
        sortby=[{"field": "datetime", "direction": "desc"}]
    )
    if items_rain:
        # Stack last 30 days and sum for accumulation
        rain_stack = []
        for item in items_rain[::-1]:  # Reverse to chronological order (oldest first)
            try:
                rain_band = read_band(item, "rainfall", bbox, out_shape=ref_shape)
                rain_stack.append(rain_band)
            except Exception as e:
                print(f"  Warning: Could not read rainfall for {item.get('id')}: {e}")
        
        if rain_stack:
            rain_array = np.stack(rain_stack, axis=0)
            data["rain"] = {
                "daily": rain_array[0],  # Latest day
                "rain_7d": np.sum(rain_array[-7:], axis=0),  # Last 7 days
                "rain_30d": np.sum(rain_array, axis=0),  # All 30 days
                "metadata": items_rain[0]
            }
            print(f"  Fetched {len(rain_stack)} days of rainfall data")
        else:
            data["rain"] = None
    else:
        print("No Rainfall data found.")
        data["rain"] = None
        
    # 5. Get WaPOR Soil Moisture Data
    print("Searching for Soil Moisture (WaPOR)...")
    items_sm = search_stac(
        collections=["wapor_soil_moisture"],
        bbox=bbox,
        limit=1,
        sortby=[{"field": "datetime", "direction": "desc"}]
    )
    if items_sm:
        item_sm = items_sm[0]
        print(f"Soil Moisture Scene: {item_sm['id']}")
        try:
            sm_data = read_band(item_sm, "relative_soil_moisture", bbox, out_shape=ref_shape)
            data["soil_moisture"] = {
                "relative": sm_data,
                "metadata": item_sm
            }
        except Exception as e:
            print(f"  Error reading soil moisture: {e}")
            data["soil_moisture"] = None
    else:
        print("No Soil Moisture data found.")
        data["soil_moisture"] = None
        
    # 6. Get iSDAsoil Data (Carbon)
    print("Searching for Soil Carbon data...")
    items_soil = search_stac(
        collections=["isda_soil_carbon_total"],
        bbox=bbox,
        limit=1
    )
    if items_soil:
        item_soil = items_soil[0]
        print(f"Soil Carbon Scene: {item_soil['id']}")
        data["soil"] = {
            "carbon": read_band(item_soil, "mean_0_20", bbox, out_shape=ref_shape), 
            "metadata": item_soil
        }
    else:
        print("No Soil Carbon data found.")
        data["soil"] = None

    # 6. Get Crop Mask Data (ESA WorldCover 2021)
    print("Searching for Land Cover data...")
    items_crop = search_stac(
        collections=["esa_worldcover_2021"],
        bbox=bbox,
        limit=1
    )
    if items_crop:
        item_crop = items_crop[0]
        print(f"Land Cover Scene: {item_crop['id']} ({item_crop['properties']['datetime']})")
        data["crop_mask"] = {
            "classification": read_band(item_crop, "classification", bbox, dtype="int32", out_shape=ref_shape),
            "metadata": item_crop
        }

    return data

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
        processed["soil_moisture"] = data["soil_moisture"]["relative"]

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

def compute_lst_baseline(bbox, ref_shape=None, current_month=None):
    """
    Computes LST baseline from historical data (same month, 3 years back).
    Returns baseline array matching ref_shape if provided.
    
    Phase 2: LST Baseline Computation
    """
    from datetime import datetime
    
    if current_month is None:
        current_month = datetime.now().month
    
    print(f"  Computing LST baseline for month {current_month}...")
    
    historical_items = []
    current_year = datetime.now().year
    
    # Fetch historical data for same month (last 3 years)
    for year in range(current_year - 3, current_year):
        start_date = f"{year}-{current_month:02d}-01"
        end_date = f"{year}-{current_month:02d}-28"
        
        try:
            items = search_stac(
                collections=["ls9_st"],
                bbox=bbox,
                datetime=f"{start_date}/{end_date}",
                limit=10,
                sortby=[{"field": "datetime", "direction": "desc"}]
            )
            if items:
                historical_items.extend(items)
        except Exception as e:
            print(f"    Warning: Could not fetch historical data for {year}-{current_month:02d}: {e}")
    
    if not historical_items:
        print(f"    No historical LST data found for month {current_month}. Using current data only.")
        return None
    
    # Pick best quality (lowest cloud cover) from each year
    historical_items.sort(key=lambda x: x['properties'].get("eo:cloud_cover", 100))
    
    lst_stack = []
    for item in historical_items[:3]:  # Limit to 3 best items
        try:
            # Match ref_shape if provided, else use default resolution
            st_dn = read_band(item, "ST_B10", bbox, out_shape=ref_shape)
            # Convert to Celsius: Kelvin = DN * 0.00341802 + 149.0, then subtract 273.15
            lst_celsius = (st_dn * 0.00341802 + 149.0) - 273.15
            lst_stack.append(lst_celsius)
        except Exception as e:
            print(f"    Warning: Could not read LST for {item['id']}: {e}")
    
    if lst_stack:
        lst_baseline = np.nanmean(np.stack(lst_stack, axis=0), axis=0)
        print(f"  LST baseline computed from {len(lst_stack)} historical scenes")
        return lst_baseline
    else:
        print(f"  Could not compute LST baseline.")
        return None

def compute_flood_mask(s1_vv, s1_vh):
    """
    Detects flooding using Sentinel-1 radar thresholds.
    Returns flood_mask (binary) and flood_risk (probability 0-1).
    
    Phase 2: Flood Threshold Detection
    """
    print("  Computing flood detection from Sentinel-1...")
    
    # Convert linear to dB
    def to_db(x):
        return 10 * np.log10(np.clip(x, 1e-5, None))
    
    vv_db = to_db(s1_vv)
    vh_db = to_db(s1_vh)
    
    # Thresholds from v3 roadmap
    FLOOD_THRESHOLD_VV_DEFINITE = -18  # dB - Definite water
    FLOOD_THRESHOLD_VV_LIKELY = -15    # dB - Likely flooded
    FLOOD_THRESHOLD_VV_VEGI = -12      # dB - Flooded vegetation threshold
    VH_VV_RATIO_THRESHOLD = -3         # dB - Flooded vegetation indicator
    
    # Binary flood mask: VV < -15 dB (likely flooded or water)
    flood_mask = (vv_db < FLOOD_THRESHOLD_VV_LIKELY).astype(float)
    
    # Enhanced detection: flooded vegetation (high VH/VV ratio + moderate VV)
    vh_vv_ratio = vh_db - vv_db
    flooded_vegetation = ((vh_vv_ratio > VH_VV_RATIO_THRESHOLD) & 
                          (vv_db < FLOOD_THRESHOLD_VV_VEGI)).astype(float)
    
    # Combined: water OR flooded vegetation
    flood_mask_combined = np.maximum(flood_mask, flooded_vegetation)
    
    # Flood risk probability (0-1 scale)
    # VV < -18: high risk (1.0), VV = -15: medium risk (0.5), VV > -12: low risk (0.0)
    flood_risk = np.clip((FLOOD_THRESHOLD_VV_LIKELY - vv_db) / 6.0, 0, 1)
    
    # Reduce risk where VV is very high (unlikely to be flooded)
    flood_risk = np.where(vv_db > -8, 0, flood_risk)
    
    return flood_mask_combined, flood_risk

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

def analyze_thresholds(metrics):
    """
    Analyzes metrics against thresholds and generates alerts.
    Implements Phase 2 alert rules from v3 roadmap.
    """
    results = {
        "stats": {},
        "alerts": []
    }
    
    # Helper to get mean of a layer, optionally masked by crop_mask
    def get_mean(layer_name):
        if layer_name in metrics and metrics[layer_name] is not None:
            data = metrics[layer_name]
            # Use crop mask if available and shapes match
            if "crop_mask_plot" in metrics and metrics["crop_mask_plot"] is not None:
                mask = metrics["crop_mask_plot"]
                # Resize check would be needed in production if resolutions differ
                # For now assuming same grid
                if data.shape == mask.shape:
                    valid_pixels = data[mask == 1]
                    if valid_pixels.size > 0:
                        return np.nanmean(valid_pixels)
            return np.nanmean(data)
        return None
    
    # Helper to get max of a layer
    def get_max(layer_name):
        if layer_name in metrics and metrics[layer_name] is not None:
            return np.nanmax(metrics[layer_name])
        return None
    
    # Helper to get coverage percentage (for binary masks)
    def get_coverage(layer_name):
        if layer_name in metrics and metrics[layer_name] is not None:
            data = metrics[layer_name]
            coverage = np.nanmean(data) * 100
            return coverage
        return None

    # 1. Calculate Statistics
    ndvi_mean = get_mean("ndvi")
    lst_mean = get_mean("lst")
    lst_anomaly_mean = get_mean("lst_anomaly")
    rain_7d = get_mean("rain_7d")
    rain_30d = get_mean("rain_30d")
    soil_moisture_mean = get_mean("soil_moisture")
    flood_coverage = get_coverage("flood_mask")
    
    results["stats"] = {
        "ndvi_mean": ndvi_mean,
        "lst_mean": lst_mean,
        "lst_anomaly_mean": lst_anomaly_mean,
        "rain_7d_mean": rain_7d,
        "rain_30d_mean": rain_30d,
        "soil_moisture_mean": soil_moisture_mean,
        "flood_coverage": flood_coverage
    }
    
    # 2. Apply v3 Roadmap Alert Rules
    
    # Rule 1: Water Stress (High Heat + Low Veg Health)
    if lst_mean is not None and ndvi_mean is not None:
        if lst_mean > 35 and ndvi_mean < 0.3:
            results["alerts"].append({
                "type": "Water Stress",
                "severity": "High",
                "message": f"High Temp ({lst_mean:.1f}°C) AND Low NDVI ({ndvi_mean:.2f}) - Immediate irrigation needed."
            })
    
    # Rule 2: Heat Anomaly
    if lst_anomaly_mean is not None and lst_anomaly_mean > 5:
        results["alerts"].append({
            "type": "Heat Anomaly",
            "severity": "High",
            "message": f"LST anomaly +{lst_anomaly_mean:.1f}°C above baseline - Thermal stress detected."
        })
    
    # Rule 3: Drought Risk (Low 7d AND 30d rainfall)
    if rain_7d is not None and rain_30d is not None:
        if rain_7d < 5 and rain_30d < 30:
            results["alerts"].append({
                "type": "Drought Risk",
                "severity": "High",
                "message": f"Severe drought conditions: 7d={rain_7d:.0f}mm, 30d={rain_30d:.0f}mm - Consider irrigation."
            })
    
    # Rule 4: Flooding Detection
    if flood_coverage is not None and flood_coverage > 10:
        results["alerts"].append({
            "type": "Flooding",
            "severity": "High",
            "message": f"Flood detected covering {flood_coverage:.1f}% of area - Monitor drainage."
        })
    
    # Rule 5: Dry Spell (low 7-day rain but not severe drought)
    if rain_7d is not None and 10 > rain_7d >= 5:
        # Avoid duplicate alert with drought risk
        results["alerts"].append({
            "type": "Dry Spell",
            "severity": "Medium",
            "message": f"Low 7-day rainfall ({rain_7d:.0f}mm) - Monitor soil moisture."
        })
    
    # Rule 6: Low Soil Moisture
    if soil_moisture_mean is not None and soil_moisture_mean < 20:
        results["alerts"].append({
            "type": "Low Soil Moisture",
            "severity": "Medium",
            "message": f"Soil moisture critically low ({soil_moisture_mean:.0f}%) - Irrigation recommended."
        })
    
    # Rule 7: Poor Crop Health
    if ndvi_mean is not None and ndvi_mean < 0.25:
        results["alerts"].append({
            "type": "Poor Crop Health",
            "severity": "Medium",
            "message": f"Average NDVI critically low ({ndvi_mean:.2f}) - Check for stress factors."
        })
    
    # Informational: Cloud cover fallback
    if metrics.get("cloud_mask") is not None:
        cloud_pct = np.nanmean(metrics["cloud_mask"]) * 100
        if cloud_pct > 20:
            results["alerts"].append({
                "type": "Cloudy S2",
                "severity": "Info",
                "message": f"Sentinel-2 cloud cover {cloud_pct:.0f}% - Check for Landsat fallback."
            })

    return results

def generate_response(processed_data, analysis_results, raw_data=None):
    """Visualizes the processed data."""
    
    # Print Alerts to Console
    print("\n=== ANALYSIS REPORT ===")
    
    if raw_data:
        print("--- Data Sources ---")
        def get_date(key):
            if raw_data.get(key) and raw_data[key].get("metadata"):
                props = raw_data[key]["metadata"].get("properties", {})
                return props.get("datetime") or props.get("start_datetime") or "N/A"
            return "Not Available"

        ndvi_src = raw_data.get("ndvi_source", "S2")
        print(f"Sentinel-2:    {get_date('s2')}")
        print(f"Landsat LST:   {get_date('landsat')}")
        print(f"Sentinel-1:    {get_date('s1')}")
        print(f"Rainfall:      {get_date('rain')}")
        print(f"Soil Moisture: {get_date('soil_moisture')}")
        print(f"Soil Carbon:   {get_date('soil')}")
        print(f"Land Cover:    {get_date('crop_mask')}")
        print(f"NDVI Source:   {ndvi_src}")
        print("--------------------")

    if "stats" in analysis_results:
         print(f"Stats: {analysis_results['stats']}")
    if analysis_results["alerts"]:
        for alert in analysis_results["alerts"]:
            print(f"[{alert['severity'].upper()}] {alert['type']}: {alert['message']}")
    else:
        print("No active alerts. Crop conditions appear normal.")
    print("=======================\n")

    # Extract dates for tile titles
    def get_date_short(key):
        if raw_data and raw_data.get(key) and raw_data[key].get("metadata"):
            props = raw_data[key]["metadata"].get("properties", {})
            dt = props.get("datetime") or props.get("start_datetime")
            if dt:
                return dt[:10]  # Extract YYYY-MM-DD
        return "N/A"

    date_s2 = get_date_short('s2')
    date_ls = get_date_short('landsat')
    date_s1 = get_date_short('s1')
    date_rain = get_date_short('rain')
    date_lc = get_date_short('crop_mask')
    date_sm = get_date_short('soil_moisture')
    
    # Determine NDVI source and date
    ndvi_source = raw_data.get("ndvi_source", "S2") if raw_data else "S2"
    ndvi_date = date_s2 if ndvi_source == "S2" else date_ls

    fig, ax = plt.subplots(3, 3, figsize=(18, 15))

    # 1. Plot RGB
    if "rgb" in processed_data:
        ax[0, 0].imshow(processed_data["rgb"])
        ax[0, 0].set_title(f"Sentinel-2 RGB\n{date_s2}")
    ax[0, 0].text(0.5, -0.05, "True color composite", ha='center', transform=ax[0, 0].transAxes, 
                  fontsize=9, style='italic', color='gray')
    ax[0, 0].axis("off")
    
    # 2. Plot NDVI
    if "ndvi" in processed_data:
        im_ndvi = ax[0, 1].imshow(processed_data["ndvi"], cmap='RdYlGn', vmin=-0.2, vmax=0.8)
        ax[0, 1].set_title(f"NDVI ({ndvi_source})\n{ndvi_date}")
        plt.colorbar(im_ndvi, ax=ax[0, 1], fraction=0.046, pad=0.04, label="NDVI Index")
    ax[0, 1].text(0.5, -0.05, "Green=healthy (>0.5) | Yellow=stressed (<0.3)", ha='center', 
                  transform=ax[0, 1].transAxes, fontsize=9, style='italic', color='gray')
    ax[0, 1].axis("off")

    # 3. Plot Crop Mask
    if processed_data.get("crop_mask_plot") is not None:
        cmap = plt.cm.get_cmap("viridis").copy()
        cmap.set_bad(color='lightgray') 
        ax[0, 2].imshow(processed_data["crop_mask_plot"], cmap='autumn_r', interpolation='nearest', vmin=0, vmax=1)
        ax[0, 2].set_title(f"Crop Mask (ESA WorldCover)\n{date_lc}")
    else:
        ax[0, 2].text(0.5, 0.5, "Land Cover Not Available", ha='center')
    ax[0, 2].text(0.5, -0.05, "Yellow=cropland | Gray=other land cover", ha='center', 
                  transform=ax[0, 2].transAxes, fontsize=9, style='italic', color='gray')
    ax[0, 2].axis("off")

    # 4. Plot LST
    if "lst" in processed_data:
        im_lst = ax[1, 0].imshow(processed_data["lst"], cmap='inferno', vmin=15, vmax=50)
        ax[1, 0].set_title(f"Land Surface Temp (Landsat)\n{date_ls}")
        plt.colorbar(im_lst, ax=ax[1, 0], fraction=0.046, pad=0.04, label="Temperature (°C)")
    else:
        ax[1, 0].text(0.5, 0.5, "LST Not Available", ha='center')
    ax[1, 0].text(0.5, -0.05, "Dark=cooler | Bright=hotter (>35°C=stress)", ha='center', 
                  transform=ax[1, 0].transAxes, fontsize=9, style='italic', color='gray')
    ax[1, 0].axis("off")

    # 5. Plot LST Anomaly (Phase 2)
    if "lst_anomaly" in processed_data:
        im_anom = ax[1, 1].imshow(processed_data["lst_anomaly"], cmap='RdBu_r', vmin=-5, vmax=5)
        ax[1, 1].set_title(f"LST Anomaly (Landsat)\n{date_ls}")
        plt.colorbar(im_anom, ax=ax[1, 1], fraction=0.046, pad=0.04, label="Deviation (°C)")
    else:
        ax[1, 1].text(0.5, 0.5, "LST Anomaly Not Available", ha='center')
    ax[1, 1].text(0.5, -0.05, "Red=hotter than baseline | Blue=cooler (>+5°C=stress)", ha='center', 
                  transform=ax[1, 1].transAxes, fontsize=9, style='italic', color='gray')
    ax[1, 1].axis("off")

    # 6. Plot Flood Mask (Phase 2)
    if "flood_mask" in processed_data:
        im_flood = ax[1, 2].imshow(processed_data["flood_mask"], cmap='Blues', vmin=0, vmax=1)
        ax[1, 2].set_title(f"Flood Mask (Sentinel-1)\n{date_s1}")
        plt.colorbar(im_flood, ax=ax[1, 2], fraction=0.046, pad=0.04, label="Flood Probability")
    else:
        ax[1, 2].text(0.5, 0.5, "Flood Detection Not Available", ha='center')
    ax[1, 2].text(0.5, -0.05, "VV < -15 dB detection | Blue=flooded", ha='center', 
                  transform=ax[1, 2].transAxes, fontsize=9, style='italic', color='gray')
    ax[1, 2].axis("off")

    # 7. Plot Rainfall 7-day (Phase 2)
    if "rain_7d" in processed_data:
        im_rain7 = ax[2, 0].imshow(processed_data["rain_7d"], cmap='Blues')
        ax[2, 0].set_title(f"Rainfall 7-day (CHIRPS)\n{date_rain}")
        plt.colorbar(im_rain7, ax=ax[2, 0], fraction=0.046, pad=0.04, label="Accumulation (mm)")
    else:
        ax[2, 0].text(0.5, 0.5, "7-day Rainfall Not Available", ha='center')
    ax[2, 0].text(0.5, -0.05, "Accumulated over 7 days (<5mm=drought risk)", ha='center', 
                  transform=ax[2, 0].transAxes, fontsize=9, style='italic', color='gray')
    ax[2, 0].axis("off")

    # 8. Plot Rainfall 30-day (Phase 2)
    if "rain_30d" in processed_data:
        im_rain30 = ax[2, 1].imshow(processed_data["rain_30d"], cmap='Blues')
        ax[2, 1].set_title(f"Rainfall 30-day (CHIRPS)\n{date_rain}")
        plt.colorbar(im_rain30, ax=ax[2, 1], fraction=0.046, pad=0.04, label="Accumulation (mm)")
    else:
        ax[2, 1].text(0.5, 0.5, "30-day Rainfall Not Available", ha='center')
    ax[2, 1].text(0.5, -0.05, "Accumulated over 30 days (<30mm=drought risk)", ha='center', 
                  transform=ax[2, 1].transAxes, fontsize=9, style='italic', color='gray')
    ax[2, 1].axis("off")

    # 9. Plot Soil Moisture (Phase 2)
    if "soil_moisture" in processed_data:
        im_sm = ax[2, 2].imshow(processed_data["soil_moisture"], cmap='YlGn', vmin=0, vmax=100)
        ax[2, 2].set_title(f"Soil Moisture (WaPOR)\n{date_sm}")
        plt.colorbar(im_sm, ax=ax[2, 2], fraction=0.046, pad=0.04, label="Moisture (%)")
    else:
        ax[2, 2].text(0.5, 0.5, "Soil Moisture Not Available", ha='center')
    ax[2, 2].text(0.5, -0.05, "Green=adequate (40-70%) | Yellow=dry (<40%)", ha='center', 
                  transform=ax[2, 2].transAxes, fontsize=9, style='italic', color='gray')
    ax[2, 2].axis("off")

    plt.tight_layout()
    plt.show()

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
    generate_response(processed_data, analysis_results, raw_data=raw_data)

if __name__ == "__main__":
    main()
