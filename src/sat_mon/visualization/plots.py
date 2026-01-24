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

    fig, ax = plt.subplots(5, 3, figsize=(18, 25))

    # --- ROW 1: Optical / Vegetation (S2) ---

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

    # 3. Plot EVI
    if "evi" in processed_data:
        im_evi = ax[0, 2].imshow(processed_data["evi"], cmap='YlGn', vmin=0, vmax=1) # EVI typical range
        ax[0, 2].set_title(f"EVI (Enhanced Veg. Index)\n{date_s2}")
        plt.colorbar(im_evi, ax=ax[0, 2], fraction=0.046, pad=0.04, label="EVI")
    else:
        ax[0, 2].text(0.5, 0.5, "EVI Not Available", ha='center')
    ax[0, 2].text(0.5, -0.05, "Improved sensitivity in high biomass", ha='center', 
                  transform=ax[0, 2].transAxes, fontsize=9, style='italic', color='gray')
    ax[0, 2].axis("off")

    # --- ROW 2: Optical / Vegetation & Water (S2) ---

    # 4. Plot SAVI
    if "savi" in processed_data:
        im_savi = ax[1, 0].imshow(processed_data["savi"], cmap='YlGn', vmin=0, vmax=1)
        ax[1, 0].set_title(f"SAVI (Soil Adjusted)\n{date_s2}")
        plt.colorbar(im_savi, ax=ax[1, 0], fraction=0.046, pad=0.04, label="SAVI")
    else:
        ax[1, 0].text(0.5, 0.5, "SAVI Not Available", ha='center')
    ax[1, 0].text(0.5, -0.05, "Corrects for soil brightness", ha='center', 
                  transform=ax[1, 0].transAxes, fontsize=9, style='italic', color='gray')
    ax[1, 0].axis("off")

    # 5. Plot NDMI
    if "ndmi" in processed_data:
        im_ndmi = ax[1, 1].imshow(processed_data["ndmi"], cmap='Blues', vmin=-0.5, vmax=0.5)
        ax[1, 1].set_title(f"NDMI (Moisture Index)\n{date_s2}")
        plt.colorbar(im_ndmi, ax=ax[1, 1], fraction=0.046, pad=0.04, label="NDMI")
    else:
        ax[1, 1].text(0.5, 0.5, "NDMI Not Available", ha='center')
    ax[1, 1].text(0.5, -0.05, "Vegetation water content", ha='center', 
                  transform=ax[1, 1].transAxes, fontsize=9, style='italic', color='gray')
    ax[1, 1].axis("off")

    # 6. Plot NDWI
    if "ndwi" in processed_data:
        im_ndwi = ax[1, 2].imshow(processed_data["ndwi"], cmap='Blues', vmin=-0.5, vmax=0.5)
        ax[1, 2].set_title(f"NDWI (Water Index)\n{date_s2}")
        plt.colorbar(im_ndwi, ax=ax[1, 2], fraction=0.046, pad=0.04, label="NDWI")
    else:
        ax[1, 2].text(0.5, 0.5, "NDWI Not Available", ha='center')
    ax[1, 2].text(0.5, -0.05, "Surface water detection", ha='center', 
                  transform=ax[1, 2].transAxes, fontsize=9, style='italic', color='gray')
    ax[1, 2].axis("off")

    # --- ROW 3: Radar (S1) & Mask ---

    # 7. Plot Flood Mask
    if "flood_mask" in processed_data:
        im_flood = ax[2, 0].imshow(processed_data["flood_mask"], cmap='Blues', vmin=0, vmax=1)
        ax[2, 0].set_title(f"Flood Mask (Sentinel-1)\n{date_s1}")
        plt.colorbar(im_flood, ax=ax[2, 0], fraction=0.046, pad=0.04, label="Flood Probability")
    else:
        ax[2, 0].text(0.5, 0.5, "Flood Detection Not Available", ha='center')
    ax[2, 0].text(0.5, -0.05, "VV < -15 dB detection", ha='center', 
                  transform=ax[2, 0].transAxes, fontsize=9, style='italic', color='gray')
    ax[2, 0].axis("off")

    # 8. Plot RVI
    if "rvi" in processed_data:
        im_rvi = ax[2, 1].imshow(processed_data["rvi"], cmap='YlGn', vmin=0, vmax=1)
        ax[2, 1].set_title(f"RVI (Radar Vegetation)\n{date_s1}")
        plt.colorbar(im_rvi, ax=ax[2, 1], fraction=0.046, pad=0.04, label="RVI")
    else:
        ax[2, 1].text(0.5, 0.5, "RVI Not Available", ha='center')
    ax[2, 1].text(0.5, -0.05, "Vegetation structure/biomass", ha='center', 
                  transform=ax[2, 1].transAxes, fontsize=9, style='italic', color='gray')
    ax[2, 1].axis("off")

    # 9. Plot Crop Mask
    if processed_data.get("crop_mask_plot") is not None:
        cmap = plt.cm.get_cmap("viridis").copy()
        cmap.set_bad(color='lightgray') 
        ax[2, 2].imshow(processed_data["crop_mask_plot"], cmap='autumn_r', interpolation='nearest', vmin=0, vmax=1)
        ax[2, 2].set_title(f"Crop Mask (ESA WorldCover)\n{date_lc}")
    else:
        ax[2, 2].text(0.5, 0.5, "Land Cover Not Available", ha='center')
    ax[2, 2].text(0.5, -0.05, "Yellow=cropland | Gray=other", ha='center', 
                  transform=ax[2, 2].transAxes, fontsize=9, style='italic', color='gray')
    ax[2, 2].axis("off")

    # --- ROW 4: Thermal & Soil (Landsat/WaPOR) ---

    # 10. Plot LST
    if "lst" in processed_data:
        im_lst = ax[3, 0].imshow(processed_data["lst"], cmap='inferno', vmin=15, vmax=50)
        ax[3, 0].set_title(f"Land Surface Temp (Landsat)\n{date_ls}")
        plt.colorbar(im_lst, ax=ax[3, 0], fraction=0.046, pad=0.04, label="Temperature (°C)")
    else:
        ax[3, 0].text(0.5, 0.5, "LST Not Available", ha='center')
    ax[3, 0].text(0.5, -0.05, "Dark=cooler | Bright=hotter", ha='center', 
                  transform=ax[3, 0].transAxes, fontsize=9, style='italic', color='gray')
    ax[3, 0].axis("off")

    # 11. Plot LST Anomaly
    if "lst_anomaly" in processed_data:
        im_anom = ax[3, 1].imshow(processed_data["lst_anomaly"], cmap='RdBu_r', vmin=-5, vmax=5)
        ax[3, 1].set_title(f"LST Anomaly (Landsat)\n{date_ls}")
        plt.colorbar(im_anom, ax=ax[3, 1], fraction=0.046, pad=0.04, label="Deviation (°C)")
    else:
        ax[3, 1].text(0.5, 0.5, "LST Anomaly Not Available", ha='center')
    ax[3, 1].text(0.5, -0.05, "Red=hotter than baseline", ha='center', 
                  transform=ax[3, 1].transAxes, fontsize=9, style='italic', color='gray')
    ax[3, 1].axis("off")

    # 12. Plot Soil Moisture
    if "soil_moisture" in processed_data:
        im_sm = ax[3, 2].imshow(processed_data["soil_moisture"], cmap='YlGn', vmin=0, vmax=100)
        ax[3, 2].set_title(f"Soil Moisture (WaPOR)\n{date_sm}")
        plt.colorbar(im_sm, ax=ax[3, 2], fraction=0.046, pad=0.04, label="Moisture (%)")
    else:
        ax[3, 2].text(0.5, 0.5, "Soil Moisture Not Available", ha='center')
    ax[3, 2].text(0.5, -0.05, "Green=adequate | Yellow=dry", ha='center', 
                  transform=ax[3, 2].transAxes, fontsize=9, style='italic', color='gray')
    ax[3, 2].axis("off")

    # --- ROW 5: Weather & Precipitation (CHIRPS/Open-Meteo) ---

    # 13. Plot Rainfall 7-day
    if "rain_7d" in processed_data:
        im_rain7 = ax[4, 0].imshow(processed_data["rain_7d"], cmap='Blues')
        ax[4, 0].set_title(f"Rainfall 7-day (CHIRPS)\n{date_rain}")
        plt.colorbar(im_rain7, ax=ax[4, 0], fraction=0.046, pad=0.04, label="Accumulation (mm)")
    else:
        ax[4, 0].text(0.5, 0.5, "7-day Rainfall Not Available", ha='center')
    ax[4, 0].text(0.5, -0.05, "Accumulated over 7 days", ha='center', 
                  transform=ax[4, 0].transAxes, fontsize=9, style='italic', color='gray')
    ax[4, 0].axis("off")

    # 14. Plot Rainfall 30-day
    if "rain_30d" in processed_data:
        im_rain30 = ax[4, 1].imshow(processed_data["rain_30d"], cmap='Blues')
        ax[4, 1].set_title(f"Rainfall 30-day (CHIRPS)\n{date_rain}")
        plt.colorbar(im_rain30, ax=ax[4, 1], fraction=0.046, pad=0.04, label="Accumulation (mm)")
    else:
        ax[4, 1].text(0.5, 0.5, "30-day Rainfall Not Available", ha='center')
    ax[4, 1].text(0.5, -0.05, "Accumulated over 30 days", ha='center', 
                  transform=ax[4, 1].transAxes, fontsize=9, style='italic', color='gray')
    ax[4, 1].axis("off")

    # 15. Plot Weather Forecast (Graph)
    if "weather" in processed_data and processed_data["weather"]:
        weather = processed_data["weather"]
        dates = [d[5:] for d in weather["dates"]] # MM-DD
        
        ax_w = ax[4, 2]
        ax_w.plot(dates, weather["temp_max"], color='red', label='Max Temp', marker='o', markersize=4)
        ax_w.plot(dates, weather["temp_min"], color='blue', label='Min Temp', marker='o', markersize=4)
        
        # Twin axis for precipitation
        ax_rain = ax_w.twinx()
        ax_rain.bar(dates, weather["precip"], color='skyblue', alpha=0.3, label='Precip')
        
        ax_w.set_title("7-Day Weather Forecast")
        ax_w.set_ylabel("Temp (°C)")
        ax_rain.set_ylabel("Precip (mm)")
        
        # Legend (combine handles)
        lines1, labels1 = ax_w.get_legend_handles_labels()
        lines2, labels2 = ax_rain.get_legend_handles_labels()
        ax_w.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize='small')
        
        ax_w.tick_params(axis='x', rotation=45, labelsize=8)
        ax_w.text(0.5, -0.05, "Temperature (C) & Precip (mm)", ha='center', 
                  transform=ax[4, 2].transAxes, fontsize=9, style='italic', color='gray')
    else:
        ax[4, 2].text(0.5, 0.5, "Weather Data Not Available", ha='center')
        ax[4, 2].axis("off")

    plt.tight_layout()
    
    # Save to file for persistence/debugging
    output_path = "latest_analysis_grid.png"
    plt.savefig(output_path, dpi=150)
    print(f"\n[Visualization] Saved analysis grid to {output_path}")
    
    # Attempt to show interactive window
    try:
        print(f"[Visualization] Attempting to display plot using backend: {plt.get_backend()}...")
        plt.show()
    except Exception as e:
        print(f"[Visualization] Could not open display window: {e}")

