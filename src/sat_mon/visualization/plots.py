import matplotlib.pyplot as plt
import numpy as np

def plot_grid(processed_data, raw_data=None):
    """Visualizes the processed data in a grid."""

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
