from flask import Flask, jsonify, render_template, request
import requests
from datetime import datetime

app = Flask(__name__)


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# --------------------------------------------------
# POLLUTANT STATUS FUNCTION
# --------------------------------------------------

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


# --------------------------------------------------
# AIR QUALITY API
# --------------------------------------------------

@app.route("/api/air-quality")
def air_quality():

    # Get city selected by the user
    city = request.args.get("city")

    # Check first before using .split()
    if not city:
        return jsonify({"error": "City is required"}), 400

    city_name = city.split(",")[0].strip()


    # --------------------------------------------------
    # STEP 1: Convert city name into coordinates
    # --------------------------------------------------

    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"

    geocoding_params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    geocoding_response = requests.get(
        geocoding_url,
        params=geocoding_params,
        timeout=10
    )

    geocoding_data = geocoding_response.json()


    # Check whether city was found
    if "results" not in geocoding_data or not geocoding_data["results"]:
        return jsonify({"error": "City not found"}), 404


    location = geocoding_data["results"][0]

    latitude = location["latitude"]
    longitude = location["longitude"]


    # --------------------------------------------------
    # STEP 2: Get air quality data
    # --------------------------------------------------

    air_quality_url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    air_quality_params = {

        "latitude": latitude,
        "longitude": longitude,

        "hourly": [
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
            "us_aqi_sulphur_dioxide"
        ],

        "timezone": "auto",

        "forecast_days": 2
    }


    air_quality_response = requests.get(
        air_quality_url,
        params=air_quality_params,
        timeout=10
    )

    air_quality_data = air_quality_response.json()


    # --------------------------------------------------
    # STEP 3: Extract hourly data
    # --------------------------------------------------

    hourly = air_quality_data["hourly"]

    times = hourly["time"]

    pm25 = hourly["pm2_5"]
    pm10 = hourly["pm10"]
    co = hourly["carbon_monoxide"]
    no2 = hourly["nitrogen_dioxide"]
    so2 = hourly["sulphur_dioxide"]
    ozone = hourly["ozone"]
    aqi = hourly["us_aqi"]

    aqi_pm25 = hourly["us_aqi_pm2_5"]
    aqi_pm10 = hourly["us_aqi_pm10"]
    aqi_no2 = hourly["us_aqi_nitrogen_dioxide"]
    aqi_co = hourly["us_aqi_carbon_monoxide"]
    aqi_ozone = hourly["us_aqi_ozone"]
    aqi_so2 = hourly["us_aqi_sulphur_dioxide"]


    # --------------------------------------------------
    # STEP 4: Find the current hour
    # --------------------------------------------------

    current_time = datetime.now()

    current_hour = current_time.strftime("%Y-%m-%dT%H:00")

    if current_hour in times:
        current_index = times.index(current_hour)
    else:
        current_index = 0


    # Get pollutant values for the current hour

    current_aqi = aqi[current_index]

    current_pm25 = pm25[current_index]
    current_pm10 = pm10[current_index]
    current_co = co[current_index]
    current_no2 = no2[current_index]
    current_so2 = so2[current_index]
    current_ozone = ozone[current_index]

    current_aqi_pm25 = aqi_pm25[current_index]
    current_aqi_pm10 = aqi_pm10[current_index]
    current_aqi_no2 = aqi_no2[current_index]
    current_aqi_co = aqi_co[current_index]
    current_aqi_ozone = aqi_ozone[current_index]
    current_aqi_so2 = aqi_so2[current_index]    


    # --------------------------------------------------
    # STEP 5: Get current-hour pollutant values
    # --------------------------------------------------

    if current_aqi <= 50:
        status = "Good"

    elif current_aqi <= 100:
        status = "Moderate"

    elif current_aqi <= 150:
        status = "Unhealthy for Sensitive Groups"

    elif current_aqi <= 200:
        status = "Unhealthy"

    elif current_aqi <= 300:
        status = "Very Unhealthy"

    else:
        status = "Hazardous"


    # --------------------------------------------------
    # STEP 6: Determine main pollutant
    # --------------------------------------------------

    pollutant_aqi_values = {
        "PM2.5": current_aqi_pm25,
        "PM10": current_aqi_pm10,
        "NO2": current_aqi_no2,
        "SO2": current_aqi_so2,
        "O3": current_aqi_ozone,
        "CO": current_aqi_co
    }

    main_pollutant = max(
        pollutant_aqi_values,
        key=pollutant_aqi_values.get
    )

    main_pollutant_aqi = pollutant_aqi_values[main_pollutant]

    total_pollutant_aqi = sum(
    value for value in pollutant_aqi_values.values()
    if value is not None
    )

    if total_pollutant_aqi > 0:
        main_pollutant_contribution = round(
        (main_pollutant_aqi / total_pollutant_aqi) * 100
        )
    else:
        main_pollutant_contribution = 0

    # --------------------------------------------------
    # STEP 7: Create pollutant data for website
    # --------------------------------------------------

    pollutants = [

        {
            "name": "PM2.5",
            "value": round(current_pm25, 1),
            "unit": "µg/m³",
            "status": pollutant_status("PM2.5", current_pm25)
        },

        {
            "name": "PM10",
            "value": round(current_pm10, 1),
            "unit": "µg/m³",
            "status": pollutant_status("PM10", current_pm10)
        },

        {
            "name": "O3",
            "value": round(current_ozone, 1),
            "unit": "µg/m³",
            "status": pollutant_status("O3", current_ozone)
        },

        {
            "name": "NO2",
            "value": round(current_no2, 1),
            "unit": "µg/m³",
            "status": pollutant_status("NO2", current_no2)
        },

        {
            "name": "SO2",
            "value": round(current_so2, 1),
            "unit": "µg/m³",
            "status": pollutant_status("SO2", current_so2)
        },

        {
            "name": "CO",
            "value": round(current_co, 1),
            "unit": "µg/m³",
            "status": pollutant_status("CO", current_co)
        }
    ]


    # --------------------------------------------------
    # STEP 8: Create hourly AQI data
    # --------------------------------------------------

    hourly_data = []

    for i in range(
        current_index,
        min(current_index + 24, len(times))
    ):
        hourly_data.append({
            "time": times[i][11:16],
            "aqi": aqi[i]
    })

    # --------------------------------------------------
    # STEP 8B: Determine best time to go out
    # --------------------------------------------------

    def format_time(time_string):

        hour, minute = map(int, time_string.split(":"))

        suffix = "AM" if hour < 12 else "PM"

        display_hour = hour % 12

        if display_hour == 0:
            display_hour = 12

        return f"{display_hour} {suffix}"


    best_start = None
    best_average_aqi = float("inf")

    for i in range(len(aqi) - 5):

        window = aqi[i:i + 6]

        if any(value is None for value in window):
            continue

        average_aqi = sum(window) / len(window)

        if average_aqi < best_average_aqi:
            best_average_aqi = average_aqi
            best_start = i


    if best_start is not None:

        start_time = times[best_start][11:16]
        end_time = times[best_start + 5][11:16]

        best_time = (
            f"{format_time(start_time)} – "
            f"{format_time(end_time)}"
        )

    else:
        best_time = "Unavailable"

    # --------------------------------------------------
    # STEP 9: Send JSON back to website
    # --------------------------------------------------

    return jsonify({

        "location": city,

        "aqi": current_aqi,

        "status": status,

        "bestTime": best_time,

        "mainPollutant": main_pollutant,

        "mainPollutantContribution": main_pollutant_contribution,

        "pollutants": pollutants,

        "hourly": hourly_data

    })


# --------------------------------------------------
# RUN SERVER
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)