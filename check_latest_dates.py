import requests
from datetime import datetime

STAC_URL = "https://explorer.digitalearth.africa/stac/search"
lat, lon, buffer = -28.736214289538538, 29.365144005056933, 0.05
bbox = [lon - buffer, lat - buffer, lon + buffer, lat + buffer]

collections = [
    "s2_l2a",                    # Sentinel-2
    "ls9_st",                    # Landsat 9
    "s1_rtc",                    # Sentinel-1
    "rainfall_chirps_daily",     # Rainfall
    "isda_soil_carbon_total",    # Soil
    "esa_worldcover_2021"        # Land Cover
]

print("Checking latest available data for each collection...")
print("=" * 70)

for collection in collections:
    try:
        payload = {
            "collections": [collection],
            "bbox": bbox,
            "limit": 1,
            "sortby": [{"field": "datetime", "direction": "desc"}]
        }
        r = requests.post(STAC_URL, json=payload, timeout=30)
        r.raise_for_status()
        js = r.json()
        
        matched = js.get('context', {}).get('matched', 0)
        features = js.get('features', [])
        
        if features:
            f = features[0]
            props = f.get('properties', {})
            dt = props.get('datetime') or props.get('start_datetime') or 'N/A'
            item_id = f.get('id', 'N/A')
            
            # Calculate age if datetime is valid
            age_str = ""
            if dt != 'N/A' and dt:
                try:
                    dt_obj = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                    now = datetime(2026, 1, 24, tzinfo=dt_obj.tzinfo)
                    age_days = (now - dt_obj).days
                    age_str = f" ({age_days} days old)"
                except:
                    pass
            
            print(f"\n{collection}:")
            print(f"  Latest: {dt}{age_str}")
            print(f"  ID: {item_id}")
            print(f"  Total scenes: {matched}")
        else:
            print(f"\n{collection}:")
            print(f"  No data found")
    except Exception as e:
        print(f"\n{collection}:")
        print(f"  Error: {e}")

print("\n" + "=" * 70)
