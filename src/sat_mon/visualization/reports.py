def print_weather_forecast(weather_data):
    """Prints the 7-day weather forecast."""
    if not weather_data or "dates" not in weather_data or "precip" not in weather_data:
        return

    print("\n--- 7-DAY WEATHER FORECAST ---")
    print(f"{'Date':<12} | {'Rain (mm)':<10} | {'Temp (°C)':<15}")
    print("-" * 45)
    
    w = weather_data
    num_days = len(w["dates"])
    # Show last 7 days (forecast)
    start_idx = max(0, num_days - 7)
    
    for i in range(start_idx, num_days):
        date = w["dates"][i]
        rain = w["precip"][i]
        t_min = w["temp_min"][i]
        t_max = w["temp_max"][i]
        
        # Highlight significant rain
        rain_str = f"{rain:.1f}"
        if rain > 5:
            rain_str += " 💧"
        
        print(f"{date:<12} | {rain_str:<10} | {t_min:.1f} - {t_max:.1f}")
    print("------------------------------")

def generate_report(processed_data, analysis_results, raw_data=None):
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
         
    # Display Risk Score (Phase 4)
    risk_score = analysis_results.get("risk_score", 0)
    risk_level = analysis_results.get("risk_level", "LOW")
    print(f"\n--- COMPOSITE RISK ASSESSMENT ---")
    print(f"Risk Score: {risk_score}/100")
    print(f"Risk Level: {risk_level}")
    print("---------------------------------")
    
    # Display Weather Forecast (v4 Feature)
    if raw_data and raw_data.get("weather"):
        print_weather_forecast(raw_data["weather"])
    
    if analysis_results["alerts"]:
        # Sort alerts by severity for display (High -> Medium -> Info)
        severity_order = {"High": 0, "Medium": 1, "Info": 2}
        sorted_alerts = sorted(analysis_results["alerts"], key=lambda x: severity_order.get(x["severity"], 99))
        
        print("\n--- ACTIVE ALERTS ---")
        for alert in sorted_alerts:
            print(f"[{alert['severity'].upper()}] {alert['type']}: {alert['message']}")
    else:
        print("\nNo active alerts. Crop conditions appear normal.")
    print("=======================\n")

def generate_historical_report(seasons, ndvi_stats, lst_stats, rain_stats):
    """
    Generates a console report for historical analysis.
    
    Args:
        seasons (list): List of detected season dictionaries.
        ndvi_stats (dict): Stats from NDVI timeseries (count, mean, etc).
        lst_stats (dict): Stats from LST timeseries.
        rain_stats (dict): Stats from Rainfall timeseries.
    """
    print("\n" + "="*50)
    print("HISTORICAL ANALYSIS REPORT")
    print("="*50 + "\n")

    # Data Summary
    print("--- DATA SUMMARY ---")
    print(f"NDVI Observations : {ndvi_stats.get('count', 0)}")
    print(f"LST Observations  : {lst_stats.get('count', 0)}")
    print(f"Total Rainfall    : {rain_stats.get('total_mm', 0):.1f} mm over {rain_stats.get('days', 0)} days")
    print("")

    # Seasons Table
    if seasons:
        print("--- DETECTED SEASONS ---")
        # Header
        print(f"{'Season':<10} | {'Planting':<12} | {'Harvest':<12} | {'Duration':<8} | {'Peak':<6} | {'Health'}")
        print("-" * 75)
        
        for season in seasons:
            # Format detection logic usually returns 'type', 'start_date', 'end_date' or similar. 
            # Looking at previous phases, 'detect_seasons' usually returns a list of dicts.
            # I will assume standard keys based on research.
            
            # Since detect_seasons isn't fully standardized in my head, I'll use .get heavily.
            # But wait, I recall 'planting_date' and 'harvest_date' from Phase B research.
            
            s_type = season.get('season_type', 'Season') # e.g. Summer/Winter
            p_date = season.get('planting_date', 'N/A')
            h_date = season.get('harvest_date', 'N/A')
            duration = season.get('duration_days', 0)
            peak = season.get('peak_ndvi', 0.0)
            health = season.get('health_rating', 'Unknown')
            
            print(f"{s_type:<10} | {p_date:<12} | {h_date:<12} | {duration:<8} | {peak:<6.2f} | {health}")
    else:
        print("No specific crop seasons detected in the analysis period.")
    
    print("\n" + "="*50 + "\n")
