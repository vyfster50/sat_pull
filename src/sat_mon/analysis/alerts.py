import numpy as np

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

    # 3. Calculate Composite Risk Score (Phase 4)
    risk_score = 0
    severity_weights = {"High": 30, "Medium": 10, "Info": 0}
    
    for alert in results["alerts"]:
        weight = severity_weights.get(alert["severity"], 0)
        risk_score += weight
    
    # Cap score at 100 for normalization
    normalized_score = min(risk_score, 100)
    
    # Determine Risk Level
    if normalized_score >= 60:
        risk_level = "CRITICAL"
    elif normalized_score >= 30:
        risk_level = "HIGH"
    elif normalized_score >= 10:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"
        
    results["risk_score"] = normalized_score
    results["risk_level"] = risk_level

    return results
