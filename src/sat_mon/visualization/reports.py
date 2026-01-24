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
