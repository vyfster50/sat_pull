import requests

def get_weather_forecast(lat, lon):
    """Fetches 7-day forecast and 5-day historical weather from Open-Meteo."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
        "past_days": 5,
        "forecast_days": 7,
        "timezone": "auto"
    }
    
    try:
        print("Fetching Weather data from Open-Meteo...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Structure for easy plotting
        weather = {
            "dates": data["daily"]["time"],
            "temp_max": data["daily"]["temperature_2m_max"],
            "temp_min": data["daily"]["temperature_2m_min"],
            "precip": data["daily"]["precipitation_sum"]
        }
        print(f"  Fetched {len(weather['dates'])} days of weather data")
        return weather
    except Exception as e:
        print(f"  Error fetching weather data: {e}")
        return None
