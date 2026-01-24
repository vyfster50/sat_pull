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
def search_stac(collections, bbox, datetime=None, limit=1, query=None):
    """Helper to search STAC API using requests."""
    payload = {
        "collections": collections,
        "bbox": bbox,
        "limit": limit
    }
    if datetime:
        payload["datetime"] = datetime
        
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

def get_satellite_data(lat, lon, buffer=0.05, start_date="2026-01-01", end_date="2026-01-24"):
    """Fetches Sentinel-2 and Crop Mask data for the location."""
    # catalog = Client.open(STAC_URL) # Removed
    bbox = get_bbox(lat, lon, buffer)
    
    data = {
        "bbox": bbox,
        "s2": None,
        "crop_mask": None,
        "landsat": None,
        "s1": None,
        "rain": None,
        "soil": None
    }

    # 1. Get Sentinel-2 Data
    print("Searching for Sentinel-2 data...")
    items_s2 = search_stac(
        collections=["s2_l2a"],
        bbox=bbox,
        datetime=f"{start_date}/{end_date}",
        limit=1
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
    
    # 2. Get Landsat 8/9 Data (LST)
    print("Searching for Landsat data...")
    try:
        # Note: Using client-side sort for clouds
        items_ls = search_stac(
            collections=["ls9_st"],
            bbox=bbox,
            datetime=f"{start_date}/{end_date}",
            limit=10 
        )
        if items_ls:
            # Sort by cloud cover (lowest first)
            items_ls.sort(key=lambda x: x['properties'].get("eo:cloud_cover", 100))
            item_ls = items_ls[0]
            
            print(f"Landsat Scene: {item_ls['id']} (Cloud: {item_ls['properties'].get('eo:cloud_cover')}%)")
            data["landsat"] = {
                "st": read_band(item_ls, "ST_B10", bbox, out_shape=ref_shape), 
                "metadata": item_ls
            }
        else:
            print("No Landsat data found.")
            data["landsat"] = None
    except Exception as e:
        print(f"Error fetching Landsat data: {e}")
        data["landsat"] = None

    # 3. Get Sentinel-1 Data (Radar)
    print("Searching for Sentinel-1 data...")
    items_s1 = search_stac(
        collections=["s1_rtc"],
        bbox=bbox,
        datetime=f"{start_date}/{end_date}",
        limit=1
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

    # 4. Get Rainfall Data (CHIRPS)
    print("Searching for Rainfall data...")
    # Rainfall might have latency, so search a bit further back
    items_rain = search_stac(
        collections=["rainfall_chirps_daily"],
        bbox=bbox,
        datetime="2025-12-01/2026-01-24",
        limit=5 
    )
    if items_rain:
        print(f"Found {len(items_rain)} Rainfall scenes")
        item_rain = items_rain[0]
        data["rain"] = {
            "daily": read_band(item_rain, "rainfall", bbox, out_shape=ref_shape),
            "metadata": item_rain
        }
    else:
        print("No Rainfall data found.")
        data["rain"] = None
        
    # 5. Get iSDAsoil Data (Carbon)
    print("Searching for Soil data...")
    items_soil = search_stac(
        collections=["isda_soil_carbon_total"],
        bbox=bbox,
        limit=1
    )
    if items_soil:
        item_soil = items_soil[0]
        print(f"Soil Scene: {item_soil['id']}")
        data["soil"] = {
            "carbon": read_band(item_soil, "mean_0_20", bbox, out_shape=ref_shape), 
            "metadata": item_soil
        }
    else:
        print("No Soil data found.")
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
    
    # Process Sentinel-2 Indices
    if data.get("s2"):
        s2 = data["s2"]
        
        # 1. RGB
        def norm(b):
            return np.clip(b / 3000, 0, 1)
        processed["rgb"] = np.dstack([norm(s2["red"]), norm(s2["green"]), norm(s2["blue"])])

        # Helper for safe division
        def safe_div(a, b):
            return np.divide(a, b, out=np.zeros_like(a), where=b!=0)

        # 2. NDVI: (NIR - Red) / (NIR + Red)
        processed["ndvi"] = safe_div((s2["nir"] - s2["red"]), (s2["nir"] + s2["red"]))

        # 3. NDRE: (NIR - RedEdge) / (NIR + RedEdge)
        processed["ndre"] = safe_div((s2["nir"] - s2["red_edge"]), (s2["nir"] + s2["red_edge"]))

        # 4. Cloud Mask (SCL)
        # SCL: 3=Shadow, 8=Medium, 9=High, 10=Cirrus
        cloud_mask = np.isin(s2["scl"], [3, 8, 9, 10])
        processed["cloud_mask"] = cloud_mask
    
    # Process Landsat LST
    if data.get("landsat"):
        st_dn = data["landsat"]["st"]
        # USGS Collection 2 ST scaling: Kelvin = DN * 0.00341802 + 149.0
        # Celsius = Kelvin - 273.15
        lst_celsius = (st_dn * 0.00341802 + 149.0) - 273.15
        processed["lst"] = lst_celsius

    # Process Sentinel-1 (Radar)
    if data.get("s1"):
        s1 = data["s1"]
        # Convert to dB: 10 * log10(x). Avoid log(0).
        def to_db(x):
            return 10 * np.log10(np.clip(x, 1e-5, None))
        
        processed["s1_vv_db"] = to_db(s1["vv"])
        processed["s1_vh_db"] = to_db(s1["vh"])

    # Process Rainfall
    if data.get("rain"):
        # Just passing it through for now
        processed["rain"] = data["rain"]["daily"]

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

def analyze_thresholds(metrics):
    """Analyzes metrics against thresholds and generates alerts."""
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

    # 1. Calculate Statistics
    ndvi_mean = get_mean("ndvi")
    lst_mean = get_mean("lst")
    rain_mean = get_mean("rain") # This is daily mean, might want sum
    
    results["stats"] = {
        "ndvi_mean": ndvi_mean,
        "lst_mean": lst_mean,
        "rain_mean": rain_mean
    }
    
    # 2. Apply Logic Rules
    # Rule 1: Water Stress (High Heat + Low Veg Health)
    if lst_mean is not None and ndvi_mean is not None:
        if lst_mean > 35 and ndvi_mean < 0.3:
            results["alerts"].append({
                "type": "Water Stress",
                "severity": "High",
                "message": f"High Temp ({lst_mean:.1f}C) and Low NDVI ({ndvi_mean:.2f}) detected."
            })
    
    # Rule 2: Irrigation Alert (Low Rain)
    if rain_mean is not None:
        if rain_mean < 1.0: # Arbitrary low daily threshold
            results["alerts"].append({
                "type": "Irrigation Needed",
                "severity": "Medium",
                "message": f"Low rainfall detected ({rain_mean:.1f}mm)."
            })

    # Rule 3: General Veg Health
    if ndvi_mean is not None and ndvi_mean < 0.25:
         results["alerts"].append({
                "type": "Poor Crop Health",
                "severity": "Medium",
                "message": f"Average NDVI is critically low ({ndvi_mean:.2f})."
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

        print(f"Sentinel-2: {get_date('s2')}")
        print(f"Landsat:    {get_date('landsat')}")
        print(f"Sentinel-1: {get_date('s1')}")
        print(f"Rainfall:   {get_date('rain')}")
        print(f"Soil:       {get_date('soil')}")
        print(f"Land Cover: {get_date('crop_mask')}")
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

    fig, ax = plt.subplots(2, 3, figsize=(18, 12))

    # 1. Plot RGB
    if "rgb" in processed_data:
        ax[0, 0].imshow(processed_data["rgb"])
        ax[0, 0].set_title(f"Sentinel-2 RGB\n{date_s2}")
    ax[0, 0].axis("off")
    
    # 2. Plot NDVI
    if "ndvi" in processed_data:
        im_ndvi = ax[0, 1].imshow(processed_data["ndvi"], cmap='RdYlGn', vmin=-0.2, vmax=0.8)
        ax[0, 1].set_title(f"NDVI (Veg. Health)\n{date_s2}")
        plt.colorbar(im_ndvi, ax=ax[0, 1], fraction=0.046, pad=0.04)
    ax[0, 1].axis("off")

    # 3. Plot Crop Mask
    if processed_data.get("crop_mask_plot") is not None:
        cmap = plt.cm.get_cmap("viridis").copy()
        cmap.set_bad(color='lightgray') 
        ax[0, 2].imshow(processed_data["crop_mask_plot"], cmap='autumn_r', interpolation='nearest', vmin=0, vmax=1)
        ax[0, 2].set_title(f"Crop Mask (Yellow)\n{date_lc}")
    else:
        ax[0, 2].text(0.5, 0.5, "Land Cover Not Available", ha='center')
    ax[0, 2].axis("off")

    # 4. Plot LST
    if "lst" in processed_data:
        im_lst = ax[1, 0].imshow(processed_data["lst"], cmap='inferno', vmin=15, vmax=50)
        ax[1, 0].set_title(f"Land Surface Temp (C)\n{date_ls}")
        plt.colorbar(im_lst, ax=ax[1, 0], fraction=0.046, pad=0.04)
    else:
        ax[1, 0].text(0.5, 0.5, "LST Not Available", ha='center')
    ax[1, 0].axis("off")

    # 5. Plot Sentinel-1 VV
    if "s1_vv_db" in processed_data:
        im_s1 = ax[1, 1].imshow(processed_data["s1_vv_db"], cmap='gray', vmin=-25, vmax=0)
        ax[1, 1].set_title(f"Sentinel-1 Radar (VV dB)\n{date_s1}")
        plt.colorbar(im_s1, ax=ax[1, 1], fraction=0.046, pad=0.04)
    else:
        ax[1, 1].text(0.5, 0.5, "Radar Not Available", ha='center')
    ax[1, 1].axis("off")

    # 6. Plot Rainfall
    if "rain" in processed_data:
        im_rain = ax[1, 2].imshow(processed_data["rain"], cmap='Blues')
        ax[1, 2].set_title(f"Daily Rainfall (mm)\n{date_rain}")
        plt.colorbar(im_rain, ax=ax[1, 2], fraction=0.046, pad=0.04)
    else:
        ax[1, 2].text(0.5, 0.5, "Rainfall Not Available", ha='center')
    ax[1, 2].axis("off")

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
    
    buffer_map = {
        "1": 0.01,
        "2": 0.05,
        "3": 0.1,
        "4": 0.2
    }
    
    if not res_input:
        buffer = default_buffer
    elif res_input in buffer_map:
        buffer = buffer_map[res_input]
    else:
        try:
            buffer = float(res_input)
        except ValueError:
            print("Invalid input. Using default resolution.")
            buffer = default_buffer
    
    return lat, lon, buffer

def main():
    setup_environment()
    
    # Interactive input
    lat, lon, buffer = get_interactive_input()
    
    # Date range (fixed for now)
    start_date = "2026-01-01"
    end_date = "2026-01-24"
    
    # Display configuration
    print(f"\n{'='*50}")
    print(f"CONFIGURATION")
    print(f"{'='*50}")
    print(f"Location: {lat}, {lon}")
    print(f"Resolution: {buffer}° (~{buffer * 111:.1f} km radius)")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"{'='*50}\n")
    
    # 1. Data Acquisition
    print("Fetching data...")
    raw_data = get_satellite_data(
        lat=lat,
        lon=lon,
        buffer=buffer,
        start_date=start_date,
        end_date=end_date
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
