import numpy as np
from typing import List, Tuple, Optional
from .stac import search_stac, get_bbox, read_band
from .weather import get_weather_forecast

def _compute_cloud_pct_from_scl(scl: np.ndarray) -> float:
    """Compute percent cloud pixels using S2 SCL classes [3, 8, 9, 10]."""
    cloud_classes = [3, 8, 9, 10]
    try:
        pct = float(np.mean(np.isin(scl, cloud_classes)) * 100.0)
    except Exception:
        pct = 100.0
    return pct


def _select_s2_item_with_cloud_threshold(
    items_s2: List[dict],
    bbox: List[float],
    threshold_pct: float = 10.0,
) -> Tuple[Optional[dict], Optional[float], Optional[dict], Optional[float]]:
    """
    From a list of recent S2 items (newest first), pick the most recent scene
    whose in-field cloud cover (via SCL) is <= threshold_pct. If none meet the
    threshold, return the lowest-cloud scene from the batch for best-effort.

    Returns:
        (selected_item, selected_cloud_pct, best_item_overall, best_cloud_pct)
    """
    selected_item = None
    selected_cloud = None
    best_item = None
    best_cloud = None

    for item in items_s2:
        try:
            scl = read_band(item, "SCL", bbox, dtype="uint8")
            cloud_pct = _compute_cloud_pct_from_scl(scl)
        except Exception as e:
            print(f"  Warning: Failed to read SCL for {item.get('id')}: {e}")
            cloud_pct = 100.0

        # Track overall best (lowest cloud) for fallback
        if (best_cloud is None) or (cloud_pct < best_cloud):
            best_cloud = cloud_pct
            best_item = item

        # If meets threshold, pick the most recent acceptable and stop
        if cloud_pct <= threshold_pct:
            selected_item = item
            selected_cloud = cloud_pct
            break

    # If none pass threshold, return best available
    if selected_item is None and best_item is not None:
        selected_item = best_item
        selected_cloud = best_cloud

    return selected_item, selected_cloud, best_item, best_cloud


def get_satellite_data(lat, lon, buffer=0.05, *, s2_cloud_threshold: float = 10.0, s2_lookback: int = 15):
    """Fetches latest satellite data for the location.

    Args:
        lat, lon: Center point
        buffer: Half-size of bbox in degrees
        s2_cloud_threshold: Max acceptable in-field cloud percent for S2 selection
        s2_lookback: Number of recent S2 items to scan (newest first)
    """
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
        "et": None,  # Added for Evapotranspiration
        "weather": None,  # Added for Open-Meteo
        "ndvi_source": None
    }

    # 0. Get Weather Data (Open-Meteo)
    data["weather"] = get_weather_forecast(lat, lon)

    # 1. Get Sentinel-2 Data (scan newest to find <= threshold cloud)
    print("Searching for Sentinel-2 data...")
    items_s2 = search_stac(
        collections=["s2_l2a"],
        bbox=bbox,
        limit=max(1, int(s2_lookback)),
        sortby=[{"field": "datetime", "direction": "desc"}]
    )

    # Reference shape (will be set by chosen S2 Red band)
    ref_shape = None

    if items_s2:
        print(f"  Found {len(items_s2)} recent S2 scenes. Evaluating cloud <= {s2_cloud_threshold:.0f}%…")
        chosen_item, chosen_cloud, best_item, best_cloud = _select_s2_item_with_cloud_threshold(
            items_s2, bbox, threshold_pct=s2_cloud_threshold
        )

        if chosen_item is None:
            print("  No usable S2 scenes found.")
        else:
            item_s2 = chosen_item
            date_str = item_s2['properties']['datetime']
            print(f"Sentinel-2 Scene Selected: {item_s2['id']} ({date_str}) | Cloud: {chosen_cloud:.1f}%")

            # Read Red band first to establish 10m grid
            red = read_band(item_s2, "B04", bbox)
            ref_shape = red.shape
            print(f"Reference Grid Shape: {ref_shape}")

            # Extract CRS if available
            epsg = item_s2.get('properties', {}).get('proj:epsg')
            if epsg:
                print(f"  Native CRS: EPSG:{epsg}")

            # Read remaining bands on the same grid
            scl = read_band(item_s2, "SCL", bbox, dtype="uint8", out_shape=ref_shape)
            data["s2"] = {
                "red": red,
                "green": read_band(item_s2, "B03", bbox, out_shape=ref_shape),
                "blue": read_band(item_s2, "B02", bbox, out_shape=ref_shape),
                "nir": read_band(item_s2, "B08", bbox, out_shape=ref_shape),
                "swir": read_band(item_s2, "B11", bbox, out_shape=ref_shape),
                "red_edge": read_band(item_s2, "B05", bbox, out_shape=ref_shape),
                "scl": scl,
                "metadata": item_s2,
                "epsg": epsg
            }

            # Check S2 cloud cover for fallback decision (use SCL just read)
            cloud_pct = _compute_cloud_pct_from_scl(scl)
            print(f"  S2 Cloud Cover (selected): {cloud_pct:.1f}%")

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
        # Use 50% threshold for NDVI fallback as before. If no S2 chosen above,
        # or if chosen cloud is very high, compute NDVI from Landsat SR.
        need_sr_fallback = False
        if data.get("s2") is None:
            need_sr_fallback = True
        else:
            try:
                scl_selected = data["s2"]["scl"]
                cloud_pct = _compute_cloud_pct_from_scl(scl_selected)
                need_sr_fallback = cloud_pct > 50.0
            except Exception:
                need_sr_fallback = False

        if items_s2 and need_sr_fallback:
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
        # Stream last 30 days and compute accumulations without stacking to save memory
        from collections import deque
        sum30 = None
        sum7 = None
        last_day = None
        window7 = deque(maxlen=7)

        count = 0
        for item in items_rain[::-1]:  # Reverse to chronological order (oldest first)
            try:
                rain_band = read_band(item, "rainfall", bbox, out_shape=ref_shape)
                count += 1
                last_day = rain_band
                # Update 30-day sum
                sum30 = rain_band if sum30 is None else (sum30 + rain_band)
                # Update 7-day rolling window
                if len(window7) == window7.maxlen:
                    # Maintain sum7 by removing oldest
                    oldest = window7[0]
                    sum7 = (sum7 - oldest) if sum7 is not None else None
                window7.append(rain_band)
                sum7 = rain_band if sum7 is None else (sum7 + rain_band)
            except Exception as e:
                print(f"  Warning: Could not read rainfall for {item.get('id')}: {e}")

        if count > 0 and last_day is not None:
            data["rain"] = {
                "daily": last_day,  # Latest day
                "rain_7d": sum7 if sum7 is not None else last_day,
                "rain_30d": sum30 if sum30 is not None else last_day,
                "metadata": items_rain[0]
            }
            print(f"  Fetched {count} days of rainfall data")
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
        
    # 5b. Get WaPOR Evapotranspiration Data (IWMI Monthly)
    print("Searching for Evapotranspiration (IWMI/WaPOR)...")
    items_et = search_stac(
        collections=["iwmi_green_et_monthly"],
        bbox=bbox,
        limit=1,
        sortby=[{"field": "datetime", "direction": "desc"}]
    )
    if items_et:
        item_et = items_et[0]
        print(f"ET Scene: {item_et['id']}")
        try:
            # Asset key for IWMI monthly is 'data'
            et_data = read_band(item_et, "data", bbox, out_shape=ref_shape)
            data["et"] = {
                "et": et_data,
                "metadata": item_et
            }
        except Exception as e:
            print(f"  Error reading ET: {e}")
            data["et"] = None
    else:
        print("No ET data found.")
        data["et"] = None

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
