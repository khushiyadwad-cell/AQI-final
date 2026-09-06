from flask import Flask, jsonify, request, send_from_directory
import requests
from datetime import datetime, timezone, timedelta
import sentry_sdk

sentry_sdk.init(
    dsn="https://239de76bba130e1faac9b4038938011c@o4512038924320768.ingest.de.sentry.io/4512038969671760",
    send_default_pii=False,
)

app = Flask(__name__)

OPEN_METEO_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_WEATHER = "https://api.open-meteo.com/v1/forecast"

# These are used only for the "Air quality elsewhere right now" cards.
FEATURED_CITIES = ["Mumbai", "Pune", "Nagpur"]


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():
    return send_from_directory("templates", "index.html")


# =========================================================
# HELPERS
# =========================================================

def pollutant_status(pollutant, value):
    if value is None:
        return "Unavailable"

    if pollutant == "PM2.5":
        if value <= 15:
            return "Good"
        elif value <= 35:
            return "Moderate"
        elif value <= 55:
            return "Unhealthy for Sensitive Groups"
        elif value <= 150:
            return "Unhealthy"
        else:
            return "Very Unhealthy"

    elif pollutant == "PM10":
        if value <= 45:
            return "Good"
        elif value <= 100:
            return "Moderate"
        elif value <= 255:
            return "Unhealthy"
        else:
            return "Very Unhealthy"

    elif pollutant == "O3":
        if value <= 60:
            return "Good"
        elif value <= 120:
            return "Moderate"
        elif value <= 180:
            return "Unhealthy"
        else:
            return "Very Unhealthy"

    elif pollutant == "NO2":
        if value <= 40:
            return "Good"
        elif value <= 80:
            return "Moderate"
        elif value <= 180:
            return "Unhealthy"
        else:
            return "Very Unhealthy"

    elif pollutant == "SO2":
        if value <= 40:
            return "Good"
        elif value <= 80:
            return "Moderate"
        elif value <= 380:
            return "Unhealthy"
        else:
            return "Very Unhealthy"

    elif pollutant == "CO":
        if value <= 4000:
            return "Good"
        elif value <= 10000:
            return "Moderate"
        elif value <= 30000:
            return "Unhealthy"
        else:
            return "Very Unhealthy"

    return "Unknown"


def overall_aqi_status(aqi):
    if aqi is None:
        return "Unavailable"

    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Moderate"
    elif aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    elif aqi <= 200:
        return "Unhealthy"
    elif aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def format_time(time_string):
    hour, minute = map(int, time_string.split(":"))

    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12

    if display_hour == 0:
        display_hour = 12

    return f"{display_hour} {suffix}"


def find_current_index(times, utc_offset_seconds):
    """
    Open-Meteo returns local times when timezone=auto is used.
    Match the current local hour as closely as possible.
    """
    if not times:
        return 0

    try:
        local_now = (
            datetime.now(timezone.utc)
            + timedelta(seconds=utc_offset_seconds or 0)
        )
        current_hour = local_now.strftime("%Y-%m-%dT%H:00")

        if current_hour in times:
            return times.index(current_hour)

        # If the exact hour is absent, choose the nearest available hour.
        target = datetime.strptime(current_hour, "%Y-%m-%dT%H:%M")
        parsed = [
            datetime.strptime(t[:16], "%Y-%m-%dT%H:%M")
            for t in times
        ]
        return min(range(len(parsed)), key=lambda i: abs(parsed[i] - target))

    except (ValueError, TypeError):
        return 0


def calculate_best_time(times, aqi):
    if not times or not aqi:
        return "Unavailable"

    best_start = None
    best_average_aqi = float("inf")

    # Six-hour window.
    for i in range(max(0, len(aqi) - 5)):
        window = aqi[i:i + 6]

        if len(window) < 6 or any(value is None for value in window):
            continue

        average_aqi = sum(window) / len(window)

        if average_aqi < best_average_aqi:
            best_average_aqi = average_aqi
            best_start = i

    if best_start is None:
        return "Unavailable"

    try:
        start_time = times[best_start][11:16]
        end_time = times[best_start + 5][11:16]

        return f"{format_time(start_time)} – {format_time(end_time)}"
    except (IndexError, ValueError):
        return "Unavailable"


def get_geocoded_city(city_name):
    params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json",
        "countryCode": "IN",
    }

    response = requests.get(
        OPEN_METEO_GEOCODING,
        params=params,
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    results = data.get("results") or []

    if not results:
        return None

    return results[0]


def get_air_quality(latitude, longitude):
    """
    Get today's hourly air-quality data.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join([
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "us_aqi",
            "us_aqi_pm2_5",
            "us_aqi_pm10",
            "us_aqi_nitrogen_dioxide",
            "us_aqi_carbon_monoxide",
            "us_aqi_ozone",
            "us_aqi_sulphur_dioxide",
        ]),
        "timezone": "auto",
        "forecast_days": 1,
    }

    response = requests.get(
        OPEN_METEO_AIR_QUALITY,
        params=params,
        timeout=10,
    )
    response.raise_for_status()

    return response.json()


def get_current_wind(latitude, longitude):
    """
    Current wind data required by the new frontend.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "kmh",
        "timezone": "auto",
    }

    response = requests.get(
        OPEN_METEO_WEATHER,
        params=params,
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    current = data.get("current") or {}

    return (
        current.get("wind_speed_10m"),
        current.get("wind_direction_10m"),
    )


def extract_current_values(air_quality_data):
    hourly = air_quality_data.get("hourly") or {}
    times = hourly.get("time") or []

    current_index = find_current_index(
        times,
        air_quality_data.get("utc_offset_seconds", 0),
    )

    def value(name):
        values = hourly.get(name) or []
        if current_index >= len(values):
            return None
        return values[current_index]

    return {
        "times": times,
        "index": current_index,
        "aqi": value("us_aqi"),
        "pm2_5": value("pm2_5"),
        "pm10": value("pm10"),
        "carbon_monoxide": value("carbon_monoxide"),
        "nitrogen_dioxide": value("nitrogen_dioxide"),
        "sulphur_dioxide": value("sulphur_dioxide"),
        "ozone": value("ozone"),
        "aqi_pm25": value("us_aqi_pm2_5"),
        "aqi_pm10": value("us_aqi_pm10"),
        "aqi_no2": value("us_aqi_nitrogen_dioxide"),
        "aqi_co": value("us_aqi_carbon_monoxide"),
        "aqi_ozone": value("us_aqi_ozone"),
        "aqi_so2": value("us_aqi_sulphur_dioxide"),
    }


def build_location_summary(city_name):
    """
    Build the compact object consumed by renderFeaturedLocations().
    If one featured city fails, simply skip it rather than breaking the
    main city's report.
    """
    try:
        location = get_geocoded_city(city_name)

        if not location:
            return None

        latitude = location.get("latitude")
        longitude = location.get("longitude")

        if latitude is None or longitude is None:
            return None

        air_data = get_air_quality(latitude, longitude)
        values = extract_current_values(air_data)

        aqi = values["aqi"]
        status = overall_aqi_status(aqi)

        if status == "Good":
            message = "Air quality is healthy. Outdoor plans are suitable for most people."
        elif status == "Moderate":
            message = "Air quality is moderate. Sensitive people should reduce prolonged outdoor exertion."
        else:
            message = "Air quality is unhealthy. Reduce strenuous outdoor activity and consider a well-fitting mask."

        return {
            "city": location.get("name", city_name),
            "state": location.get("admin1", ""),
            "aqi": aqi,
            "status": status,
            "message": message,
        }

    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


# =========================================================
# AIR QUALITY API
# =========================================================

@app.route("/api/air-quality")
def air_quality():
    print("AIR QUALITY ROUTE HIT")
    city = request.args.get("city", "").strip()

    if not city:
        return jsonify({
            "error": "City is required"
        }), 400

    # The frontend sends the verified Open-Meteo city name.
    # Strip anything after a comma for inputs such as "Mumbai, Maharashtra".
    city_name = city.split(",")[0].strip()

    # ---------------------------------------------------------
    # STEP 1 — GEOCODING
    # ---------------------------------------------------------

    try:
        location = get_geocoded_city(city_name)

    except requests.RequestException as error:
        return jsonify({
            "error": "Unable to contact location service",
            "details": str(error),
        }), 502

    if not location:
        return jsonify({
            "error": "Indian city not found"
        }), 404

    latitude = location.get("latitude")
    longitude = location.get("longitude")

    if latitude is None or longitude is None:
        return jsonify({
            "error": "Location coordinates unavailable"
        }), 502

    city_result = location.get("name", city_name)
    state = location.get("admin1", "")

    # ---------------------------------------------------------
    # STEP 2 — WIND DATA
    # ---------------------------------------------------------

    try:
        current_wind_speed, current_wind_direction = get_current_wind(
            latitude,
            longitude,
        )
    except Exception as e:
        print("WIND API ERROR:", repr(e))
        current_wind_speed = None
        current_wind_direction = None

    # ---------------------------------------------------------
    # STEP 3 — AIR QUALITY DATA
    # ---------------------------------------------------------

    try:
        air_quality_data = get_air_quality(latitude, longitude)

    except requests.RequestException as error:
        return jsonify({
            "error": "Unable to contact air quality service",
            "details": str(error),
        }), 502

    try:
        current = extract_current_values(air_quality_data)

        times = current["times"]
        current_aqi = current["aqi"]

        pm25 = current["pm2_5"]
        pm10 = current["pm10"]
        co = current["carbon_monoxide"]
        no2 = current["nitrogen_dioxide"]
        so2 = current["sulphur_dioxide"]
        ozone = current["ozone"]

        aqi_pm25 = current["aqi_pm25"]
        aqi_pm10 = current["aqi_pm10"]
        aqi_no2 = current["aqi_no2"]
        aqi_co = current["aqi_co"]
        aqi_ozone = current["aqi_ozone"]
        aqi_so2 = current["aqi_so2"]

    except (KeyError, TypeError, IndexError):
        return jsonify({
            "error": "Unexpected air quality response from Open-Meteo"
        }), 502

    # ---------------------------------------------------------
    # STEP 4 — OVERALL AQI STATUS
    # ---------------------------------------------------------

    status = overall_aqi_status(current_aqi)

    # ---------------------------------------------------------
    # STEP 5 — MAIN POLLUTANT
    # ---------------------------------------------------------

    pollutant_aqi_values = {
        "PM2.5": aqi_pm25,
        "PM10": aqi_pm10,
        "NO2": aqi_no2,
        "SO2": aqi_so2,
        "O3": aqi_ozone,
        "CO": aqi_co,
    }

    valid_pollutant_aqi = {
        pollutant: value
        for pollutant, value in pollutant_aqi_values.items()
        if value is not None
    }

    if valid_pollutant_aqi:
        main_pollutant = max(
            valid_pollutant_aqi,
            key=valid_pollutant_aqi.get,
        )
        main_pollutant_aqi = valid_pollutant_aqi[main_pollutant]
    else:
        main_pollutant = None
        main_pollutant_aqi = None

    # ---------------------------------------------------------
    # STEP 6 — MAIN POLLUTANT CONTRIBUTION
    # ---------------------------------------------------------

    total_pollutant_aqi = sum(valid_pollutant_aqi.values())

    if main_pollutant_aqi is not None and total_pollutant_aqi > 0:
        main_pollutant_contribution = round(
            (main_pollutant_aqi / total_pollutant_aqi) * 100
        )
    else:
        main_pollutant_contribution = 0

    # ---------------------------------------------------------
    # STEP 7 — BEST TIME TO GO OUT
    # ---------------------------------------------------------

    hourly_aqi = air_quality_data.get("hourly", {}).get("us_aqi") or []
    best_time = calculate_best_time(times, hourly_aqi)

    # ---------------------------------------------------------
    # STEP 8 — FEATURED LOCATIONS
    # ---------------------------------------------------------
    #
    # The new HTML explicitly looks for:
    #   data.featured_locations
    # or
    #   data.nearby_locations
    #
    # Supplying featured_locations keeps that section live instead of
    # leaving the three loading cards on screen.

    featured_locations = []

    for featured_city in FEATURED_CITIES:
        # Don't waste a second API request for the city already being viewed.
        if featured_city.lower() == city_result.lower():
            continue

        summary = build_location_summary(featured_city)

        if summary:
            featured_locations.append(summary)

        if len(featured_locations) >= 3:
            break

    # ---------------------------------------------------------
    # STEP 9 — RETURN DATA FOR NEW FRONTEND
    # ---------------------------------------------------------

    return jsonify({
        "city": city_result,
        "state": state,
        "location": city_result,

        "latitude": latitude,
        "longitude": longitude,

        "aqi": current_aqi,
        "status": status,
        "best_time": best_time,

        "mainPollutant": main_pollutant,
        "mainPollutantContribution": main_pollutant_contribution,

        # Current pollutant values
        "pm2_5": pm25,
        "pm10": pm10,
        "carbon_monoxide": co,
        "nitrogen_dioxide": no2,
        "sulphur_dioxide": so2,
        "ozone": ozone,

        # Keep the pollutant object for the frontend's flexible
        # getValue() lookup.
        "pollutants": {
            "pm2_5": pm25,
            "pm10": pm10,
            "carbon_monoxide": co,
            "nitrogen_dioxide": no2,
            "sulphur_dioxide": so2,
            "ozone": ozone,
        },

        # Hourly AQI expected by renderAirData()
        "hourly": {
            "time": times,
            "aqi": hourly_aqi,
            "us_aqi": hourly_aqi,
        },

        # Current wind data expected by the new frontend
        "wind_speed": current_wind_speed,
        "wind_direction": current_wind_direction,

        # New homepage location cards
        "featured_locations": featured_locations,
    })


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
