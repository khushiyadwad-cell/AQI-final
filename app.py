from flask import Flask, jsonify, render_template, request
import requests
from datetime import datetime, timezone, timedelta

app = Flask(__name__)


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# POLLUTANT STATUS
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


# =========================================================
# AIR QUALITY API
# =========================================================

@app.route("/api/air-quality")
def air_quality():

    city = request.args.get("city")
    language = request.args.get("language", "en")

    if not city:
        return jsonify({
            "error": "City is required"
        }), 400

    city_name = city.split(",")[0].strip()

    marathi_city_map = {
        "मुंबई": "Mumbai",
        "पुणे": "Pune",
        "ठाणे": "Thane",
        "नागपूर": "Nagpur",
        "नाशिक": "Nashik",
        "छत्रपती संभाजीनगर": "Chhatrapati Sambhajinagar",
        "कोल्हापूर": "Kolhapur",
        "सोलापूर": "Solapur",
        "अमरावती": "Amravati",
        "सातारा": "Satara",
        "रत्नागिरी": "Ratnagiri",
        "अकोला": "Akola",
        "नांदेड": "Nanded",
        "लातूर": "Latur",
        "जळगाव": "Jalgaon"
    }

    if language == "mr":
        city_name = marathi_city_map.get(city_name, city_name)

    # =====================================================
    # STEP 1 — GEOCODING
    # =====================================================

    geocoding_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )

    geocoding_params = {
        "name": city_name,
        "count": 1,
        "language": language,
        "format": "json",
        "countryCode": "IN"
    }

    try:

        geocoding_response = requests.get(
            geocoding_url,
            params=geocoding_params,
            timeout=10
        )

        geocoding_response.raise_for_status()

        geocoding_data = geocoding_response.json()

    except requests.RequestException as error:

        return jsonify({
            "error": "Unable to contact location service",
            "details": str(error)
        }), 502


    if (
        "results" not in geocoding_data
        or not geocoding_data["results"]
    ):

        return jsonify({
            "error": "Indian city not found"
        }), 404


    location = geocoding_data["results"][0]

    latitude = location["latitude"]
    longitude = location["longitude"]

    city_result = location.get(
        "name",
        city_name
    )

    state = location.get(
        "admin1",
        ""
    )


    # =====================================================
    # STEP 2 — AIR QUALITY DATA
    # =====================================================

    air_quality_url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
    )

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

        "forecast_days": 1
    }


    try:

        air_quality_response = requests.get(
            air_quality_url,
            params=air_quality_params,
            timeout=10
        )

        air_quality_response.raise_for_status()

        air_quality_data = (
            air_quality_response.json()
        )

    except requests.RequestException as error:

        return jsonify({
            "error": "Unable to contact air quality service",
            "details": str(error)
        }), 502


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


    # =====================================================
    # STEP 3 — FIND CURRENT HOUR
    # =====================================================

    current_index = 0

    timezone_offset = air_quality_data.get(
        "utc_offset_seconds",
        0
    )

    local_now = (
        datetime.now(timezone.utc)
        + timedelta(seconds=timezone_offset)
    )

    current_hour = local_now.strftime(
        "%Y-%m-%dT%H:00"
    )

    if current_hour in times:

        current_index = times.index(
            current_hour
        )


    # =====================================================
    # STEP 4 — CURRENT VALUES
    # =====================================================

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


    # =====================================================
    # STEP 5 — OVERALL AQI STATUS
    # =====================================================

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


    # =====================================================
    # STEP 6 — MAIN POLLUTANT
    # =====================================================

    pollutant_aqi_values = {

        "PM2.5": current_aqi_pm25,

        "PM10": current_aqi_pm10,

        "NO2": current_aqi_no2,

        "SO2": current_aqi_so2,

        "O3": current_aqi_ozone,

        "CO": current_aqi_co
    }


    valid_pollutant_aqi = {

        pollutant: value

        for pollutant, value
        in pollutant_aqi_values.items()

        if value is not None
    }


    if valid_pollutant_aqi:

        main_pollutant = max(
            valid_pollutant_aqi,
            key=valid_pollutant_aqi.get
        )

        main_pollutant_aqi = (
            valid_pollutant_aqi[main_pollutant]
        )

    else:

        main_pollutant = None

        main_pollutant_aqi = None


    # =====================================================
    # STEP 7 — MAIN POLLUTANT CONTRIBUTION
    # =====================================================

    total_pollutant_aqi = sum(
        value
        for value in valid_pollutant_aqi.values()
        if value is not None
    )


    if (
        main_pollutant_aqi is not None
        and total_pollutant_aqi > 0
    ):

        main_pollutant_contribution = round(
            (
                main_pollutant_aqi
                / total_pollutant_aqi
            ) * 100
        )

    else:

        main_pollutant_contribution = 0


    # =====================================================
    # STEP 8 — BEST TIME TO GO OUT
    # =====================================================

    def format_time(time_string):

        hour, minute = map(
            int,
            time_string.split(":")
        )

        suffix = (
            "AM"
            if hour < 12
            else "PM"
        )

        display_hour = hour % 12

        if display_hour == 0:
            display_hour = 12

        return f"{display_hour} {suffix}"


    best_start = None
    best_average_aqi = float("inf")


    for i in range(
        len(aqi) - 5
    ):

        window = aqi[i:i + 6]

        if any(
            value is None
            for value in window
        ):
            continue

        average_aqi = (
            sum(window)
            / len(window)
        )

        if (
            average_aqi
            < best_average_aqi
        ):

            best_average_aqi = (
                average_aqi
            )

            best_start = i


    if best_start is not None:

        start_time = (
            times[best_start][11:16]
        )

        end_time = (
            times[best_start + 5][11:16]
        )

        best_time = (
            f"{format_time(start_time)} – "
            f"{format_time(end_time)}"
        )

    else:

        best_time = "Unavailable"


    # =====================================================
    # STEP 9 — RETURN DATA FOR NEW FRONTEND
    # =====================================================

    return jsonify({

        "city": city_result,

        "state": state,

        "location": city_result,

        "aqi": current_aqi,

        "status": status,

        "best_time": best_time,

        "mainPollutant": main_pollutant,

        "mainPollutantContribution":
            main_pollutant_contribution,


        # -----------------------------------------------
        # CURRENT POLLUTANT VALUES
        # -----------------------------------------------

        "pm2_5": current_pm25,

        "pm10": current_pm10,

        "carbon_monoxide": current_co,

        "nitrogen_dioxide": current_no2,

        "sulphur_dioxide": current_so2,

        "ozone": current_ozone,


        # -----------------------------------------------
        # ALSO KEEP POLLUTANT OBJECT
        # -----------------------------------------------

        "pollutants": {

            "pm2_5": current_pm25,

            "pm10": current_pm10,

            "carbon_monoxide": current_co,

            "nitrogen_dioxide": current_no2,

            "sulphur_dioxide": current_so2,

            "ozone": current_ozone
        },


        # -----------------------------------------------
        # HOURLY AQI
        # -----------------------------------------------

        "hourly": {

            "time": times,

            "aqi": aqi
        }

    })


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
