-- Examples: Last-N readings for a machine

-- Newest → Oldest
SELECT time, vibration, temperature, rpm
FROM sensors_readings
WHERE machine_id = 'M1'
ORDER BY time DESC
LIMIT 10;

-- Oldest → Newest (for ML models)
WITH last_n AS (
  SELECT time, vibration, temperature, rpm
  FROM sensors_readings
  WHERE machine_id = 'M1'
  ORDER BY time DESC
  LIMIT 10
)
SELECT * FROM last_n
ORDER BY time ASC;
