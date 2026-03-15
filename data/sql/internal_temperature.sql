
-- Extract temperature for a given device. Table: temperature (change if yours differs).
SELECT
    datetime               AS timestamp,
    value AS temperature_celsius
FROM reading_temperature
WHERE ref= :itish_int_temp
ORDER BY datetime desc;