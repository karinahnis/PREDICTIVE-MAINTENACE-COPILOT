-- 001_create_tables.sql
-- Run this once as the DB migration (kalau kamu mau pakai SQL langsung)

-- 1) Enable TimescaleDB extension (opsional tapi direkomendasikan)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 2) Machines table (sesuai class Machine di models.py)
CREATE TABLE IF NOT EXISTS machines (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(50) UNIQUE NOT NULL, -- M1, M2, M3
    name VARCHAR(200),
    location VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Insert three machines (dummy awal)
INSERT INTO machines (machine_id, name, location)
VALUES
  ('M1', 'Machine 1', 'Plant A'),
  ('M2', 'Machine 2', 'Plant A'),
  ('M3', 'Machine 3', 'Plant A')
ON CONFLICT (machine_id) DO NOTHING;

-- 3) Sensor readings hypertable (sesuai class SensorReading di models.py)
CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    machine_id VARCHAR(50) NOT NULL,
    air_temperature DOUBLE PRECISION,
    process_temperature DOUBLE PRECISION,
    rotational_speed DOUBLE PRECISION,
    torque DOUBLE PRECISION,
    tool_wear DOUBLE PRECISION,
    raw_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Convert to hypertable pada kolom "time"
SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);

-- Index untuk query cepat
CREATE INDEX IF NOT EXISTS idx_sensor_readings_machine_time
    ON sensor_readings (machine_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_time
    ON sensor_readings (time DESC);

-- 4) Predictions table (sesuai class Prediction di models.py)
CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT now(),
    machine_id VARCHAR(50) NOT NULL,
    window_n INTEGER,
    probability DOUBLE PRECISION,
    failure_type VARCHAR(100),
    failure_name VARCHAR(200),
    explanation TEXT,
    model_version VARCHAR(100),
    raw_input JSONB,
    raw_output JSONB
);

CREATE INDEX IF NOT EXISTS idx_predictions_machine_time
    ON predictions (machine_id, time DESC);

-- 5) Tickets table (sesuai class Ticket di models.py)
CREATE TABLE IF NOT EXISTS tickets (
    id BIGSERIAL PRIMARY KEY,
    machine_id VARCHAR(50) NOT NULL,
    created_by VARCHAR(100),
    severity VARCHAR(20),
    status VARCHAR(20) DEFAULT 'open',
    message TEXT,
    probability DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tickets_machine_id
    ON tickets (machine_id);
