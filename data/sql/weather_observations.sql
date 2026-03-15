
-- External weather (hourly). Filter by postcode_district for your area.
-- Only columns useful for energy: temp, humidity, solar, wind, precipitation, comfort indices.
SELECT
    time                  AS timestamp,
    temperature_celsius,
    humidity_percent,
    precipitation_mm,
    wind_speed_kmh,
    cloud_cover_percent,
    solar_energy_mj,
    solar_radiation_w,
    heat_index_celsius,
    wind_chill_celsius
FROM weather_observations
WHERE postcode_district = :postcode_district
ORDER BY time desc;