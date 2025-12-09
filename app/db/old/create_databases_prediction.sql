
# create_predictions_table.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.predictions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  sensor_reading_id uuid,
  machine_id text,
  time timestamptz,
  model_version text,
  prediction_label text,
  failure_probability double precision,
  raw_scores jsonb,
  raw_features jsonb,
  metadata jsonb,
  created_at timestamptz DEFAULT now()
);

# optional FK
# ALTER TABLE public.predictions ADD CONSTRAINT fk_sensor_reading FOREIGN KEY(sensor_reading_id) REFERENCES public.sensors_readings(id);