import numpy as np
from datetime import datetime
from ..data.stac import search_stac, read_band

def compute_lst_baseline(bbox, ref_shape=None, current_month=None):
    """
    Computes LST baseline from historical data (same month, 3 years back).
    Returns baseline array matching ref_shape if provided.
    
    Phase 2: LST Baseline Computation
    """
    
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
