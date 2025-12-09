# backend/app/services/db_service.py
from dotenv import load_dotenv
load_dotenv()

import os
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger("db_service")
# if no logging configured upstream, show debug to console for local dev
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.DEBUG)

# Try imports for SQLAlchemy
try:
    from sqlalchemy import (
        create_engine,
        MetaData,
        Table,
        Column,
        TIMESTAMP,
        Float,
        Integer,
        String,
        text,
        select,
        insert,
    )
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.exc import SQLAlchemyError
    sqlalchemy_available = True
except Exception as e:
    logger.debug("sqlalchemy import failed: %s", e)
    sqlalchemy_available = False

# Import settings (will read .env via pydantic BaseSettings)
try:
    from app.core.config import get_settings
    settings = get_settings()
except Exception as e:
    logger.debug("failed to import settings from app.core.config: %s", e)
    settings = None


def _build_database_url_from_settings() -> Optional[str]:
    """
    Build a SQLAlchemy URL from individual DB settings (if available).
    Returns None if not enough information.
    """
    if not settings:
        return None

    host = getattr(settings, "DB_HOST", None)
    port = getattr(settings, "DB_PORT", None)
    dbname = getattr(settings, "DB_NAME", None)
    user = getattr(settings, "DB_USER", None)
    pwd = getattr(settings, "DB_PASS", None)

    if not (host and dbname and user):
        return None

    port_part = f":{port}" if port else ""
    # include password only if provided (non-empty)
    auth_part = f"{user}:{pwd}" if pwd else f"{user}"
    return f"postgresql+psycopg2://{auth_part}@{host}{port_part}/{dbname}"


# Prefer a full DATABASE_URL env var (if provided and looks like a URL)
env_db_url = os.getenv("DATABASE_URL", None)
DATABASE_URL: Optional[str] = None
if env_db_url and "://" in env_db_url:
    DATABASE_URL = env_db_url
else:
    # either DATABASE_URL not set or is not a URL (e.g. 'localhost'), build from parts
    DATABASE_URL = _build_database_url_from_settings()

logger.debug("db_service: final DATABASE_URL = %r", DATABASE_URL)

# In-memory fallback store
_memory_store: List[Dict[str, Any]] = []
_memory_store_predictions: List[Dict[str, Any]] = []

# SQLAlchemy engine/table placeholders
_engine = None
_sensor_table = None
_predictions_table = None
_metadata = None


def _now_as_dt(val: Optional[Any]) -> datetime:
    """Normalize incoming time value to datetime (UTC-aware if possible)."""
    if val is None:
        return datetime.utcnow()
    if isinstance(val, datetime):
        return val
    try:
        # handle ISO strings that may end with Z
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        try:
            ts = float(val)
            return datetime.utcfromtimestamp(ts)
        except Exception:
            return datetime.utcnow()


# Initialize SQLAlchemy engine and tables if possible
if sqlalchemy_available and DATABASE_URL:
    try:
        _engine = create_engine(DATABASE_URL, future=True)
        _metadata = MetaData()

        # table matching Kaggle features, name: sensor_readings
        _sensor_table = Table(
            "sensor_readings",
            _metadata,
            Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")),
            Column("ts", TIMESTAMP(timezone=True), nullable=False),
            Column("machine_id", String, nullable=False),
            Column("air_temperature", Float),
            Column("process_temperature", Float),
            Column("rotational_speed", Integer),
            Column("torque", Float),
            Column("tool_wear", Integer),
            Column("metadata", JSONB),
            Column("created_at", TIMESTAMP(timezone=True), server_default=text("now()")),
        )

        # predictions table
        _predictions_table = Table(
            "predictions",
            _metadata,
            Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")),
            Column("sensor_reading_id", UUID(as_uuid=True)),
            Column("machine_id", String),
            Column("ts", TIMESTAMP(timezone=True)),
            Column("model_version", String),
            Column("prediction_label", String),
            Column("failure_probability", Float),
            Column("raw_scores", JSONB),
            Column("raw_features", JSONB),
            Column("metadata", JSONB),
            Column("created_at", TIMESTAMP(timezone=True), server_default=text("now()")),
        )

        # Create extension and tables (safe for dev)
        with _engine.begin() as conn:
            # create uuid function if not exists
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        _metadata.create_all(_engine)
        logger.info("db_service: connected to DB and ensured tables exist.")
    except SQLAlchemyError as e:
        logger.exception("db_service: failed to initialize SQLAlchemy engine; falling back to memory store. Error: %s", e)
        _engine = None
        _sensor_table = None
        _predictions_table = None
    except Exception as e:
        logger.exception("db_service: unexpected error while initializing DB engine; falling back to memory store. Error: %s", e)
        _engine = None
        _sensor_table = None
        _predictions_table = None
else:
    if not sqlalchemy_available:
        logger.debug("db_service: SQLAlchemy not available; using in-memory store.")
    else:
        logger.debug("db_service: DATABASE_URL not set or incomplete; using in-memory store.")


def insert_reading(payload: Dict[str, Any]) -> str:
    """
    Insert a sensor reading. Returns inserted_id (UUID string).
    Expected payload keys:
      - machine_id, time or ts, air_temperature, process_temperature,
        rotational_speed, torque, tool_wear, metadata (dict)
    """
    data = dict(payload)
    inserted_id = str(uuid.uuid4())

    # Accept both 'time' and 'ts' from payload
    time_val = data.get("time") or data.get("ts")
    data_time = _now_as_dt(time_val)

    metadata_obj = data.get("metadata") or {}
    try:
        json.dumps(metadata_obj)
    except Exception:
        metadata_obj = {"raw_metadata": str(metadata_obj)}

    insert_values = {
        "id": inserted_id,
        "ts": data_time,
        "machine_id": data.get("machine_id") or data.get("machineId") or "unknown",
        "air_temperature": data.get("air_temperature"),
        "process_temperature": data.get("process_temperature"),
        "rotational_speed": data.get("rotational_speed"),
        "torque": data.get("torque"),
        "tool_wear": data.get("tool_wear"),
        "metadata": metadata_obj,
    }

    # try DB insert
    if _engine is not None and _sensor_table is not None:
        try:
            with _engine.begin() as conn:
                stmt = insert(_sensor_table).values(**insert_values)
                conn.execute(stmt)
            logger.debug("db_service: inserted reading into DB: %s", insert_values)
            return inserted_id
        except Exception as e:
            logger.exception("db_service: DB insert failed, falling back to in-memory store. Error: %s", e)

    # fallback: memory
    try:
        record = dict(insert_values)
        # store time as ISO string in memory
        record["ts"] = data_time.isoformat()
        _memory_store.append(record)
        logger.debug("db_service: inserted reading into memory store: %s", record)
    except Exception as e:
        logger.exception("db_service: failed to append to memory store: %s", e)

    return inserted_id


def fetch_readings(machine_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Fetch readings for GET /ingest.
    Returns list of dict rows (most recent first).
    """
    if _engine is not None and _sensor_table is not None:
        try:
            stmt = select(_sensor_table).order_by(_sensor_table.c.ts.desc()).limit(limit).offset(offset)
            if machine_id:
                stmt = stmt.where(_sensor_table.c.machine_id == machine_id)
            with _engine.connect() as conn:
                rows = conn.execute(stmt).fetchall()
                result = [dict(r) for r in rows]
                return result
        except Exception as e:
            logger.exception("db_service: DB query failed: %s", e)
            return []

    # fallback to memory store - filter & paging
    filtered = [r for r in _memory_store if (machine_id is None or r.get("machine_id") == machine_id)]
    # memory store kept in append order; want newest first by ts if possible
    try:
        # if ts stored as ISO strings, sort descending
        filtered_sorted = sorted(filtered, key=lambda x: x.get("ts", ""), reverse=True)
    except Exception:
        filtered_sorted = filtered[::-1]
    start = offset
    end = offset + limit
    return filtered_sorted[start:end]


def get_recent(machine_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Return last `limit` readings (DB if available, else memory)."""
    # reuse fetch_readings with offset 0
    return fetch_readings(machine_id=machine_id, limit=limit, offset=0)


def insert_prediction(record: Dict[str, Any]) -> str:
    """Insert prediction into DB (or memory fallback). Returns prediction id."""
    pred_id = str(uuid.uuid4())
    rec = {
        "id": pred_id,
        "sensor_reading_id": record.get("sensor_reading_id"),
        "machine_id": record.get("machine_id"),
        "ts": record.get("time") or record.get("ts"),
        "model_version": record.get("model_version"),
        "prediction_label": record.get("prediction_label"),
        "failure_probability": record.get("failure_probability"),
        "raw_scores": record.get("raw_scores"),
        "raw_features": record.get("raw_features"),
        "metadata": record.get("metadata"),
    }

    # try DB insert
    if _engine is not None and _predictions_table is not None:
        try:
            with _engine.begin() as conn:
                conn.execute(insert(_predictions_table).values(**rec))
            return pred_id
        except Exception as e:
            logger.exception('insert_prediction: DB insert failed, fallback to memory: %s', e)

    # fallback: append to memory store
    try:
        _memory_store_predictions.append(rec)
    except Exception:
        pass

    return pred_id


def fetch_predictions(machine_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Fetch prediction records.
    Returns list of dict rows (most recent first).
    """
    if _engine is not None and _predictions_table is not None:
        try:
            stmt = select(_predictions_table).order_by(_predictions_table.c.created_at.desc()).limit(limit).offset(offset)
            if machine_id:
                stmt = stmt.where(_predictions_table.c.machine_id == machine_id)
            with _engine.connect() as conn:
                rows = conn.execute(stmt).fetchall()
                result = [dict(r) for r in rows]
                return result
        except Exception as e:
            logger.exception("db_service: DB query for predictions failed: %s", e)
            return []

    # fallback to memory store
    filtered = [r for r in _memory_store_predictions if (machine_id is None or r.get("machine_id") == machine_id)]
    try:
        filtered_sorted = sorted(filtered, key=lambda x: x.get("created_at", x.get("ts", "")), reverse=True)
    except Exception:
        filtered_sorted = filtered[::-1]
    start = offset
    end = offset + limit
    return filtered_sorted[start:end]


def get_memory_store():
    return list(_memory_store)

def get_memory_predictions():
    return list(_memory_store_predictions)
