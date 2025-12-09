import logging
import re
from typing import Optional, List, Any, Dict


from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text


from app.api.v1.predictions import compute_risk
from app.services.db_service import _engine, _sensor_table, _predictions_table
from app.api.v1.machine_utils import (
    PredictionResult,
    row_to_dict_safe,
    parse_metadata,
    parse_timestamp,
)

router = APIRouter(prefix="/machines", tags=["machines"])
logger = logging.getLogger("machines")


# ============================================================
# MODELS
# ============================================================
class Reading(BaseModel):
    ts: datetime
    air_temperature: Optional[float]
    process_temperature: Optional[float]
    rotational_speed: Optional[int]
    torque: Optional[float]
    tool_wear: Optional[int]
    prediction: Optional[PredictionResult] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================
# GET /machines/{machine_id}/recent
# ============================================================
@router.get("/{machine_id}/recent", response_model=List[Reading])
def recent(machine_id: str, limit: int = Query(50, gt=0, le=2000)):
    stmt = (
        select(
            _sensor_table.c.id,
            _sensor_table.c.ts,
            _sensor_table.c.air_temperature,
            _sensor_table.c.process_temperature,
            _sensor_table.c.rotational_speed,
            _sensor_table.c.torque,
            _sensor_table.c.tool_wear,
            _sensor_table.c.metadata,
            _predictions_table.c.id.label("prediction_id"),
            _predictions_table.c.model_version,
            _predictions_table.c.prediction_label,
            _predictions_table.c.failure_probability,
            _predictions_table.c.metadata.label("prediction_metadata"),
        )
        .outerjoin(_predictions_table, _sensor_table.c.id == _predictions_table.c.sensor_reading_id)
        .where(_sensor_table.c.machine_id == machine_id)
        .order_by(_sensor_table.c.created_at.desc())
        .limit(limit)
    )

    try:
        with _engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
    except Exception:
        raise HTTPException(500, "Database query failed")

    results: List[Reading] = []
    for r in rows:
        d = row_to_dict_safe(r)

        prediction = None
        if d.get("prediction_id") is not None:
            prediction = PredictionResult(
                prediction_id=str(d["prediction_id"]),
                model_name=d.get("model_version"),
                label=d.get("prediction_label"),
                score=d.get("failure_probability"),
                meta=parse_metadata(d.get("prediction_metadata")),
            )

        results.append(
            Reading(
                ts=parse_timestamp(d["ts"]),
                air_temperature=d["air_temperature"],
                process_temperature=d["process_temperature"],
                rotational_speed=d["rotational_speed"],
                torque=d["torque"],
                tool_wear=d["tool_wear"],
                metadata=parse_metadata(d["metadata"]),
                prediction=prediction,
            )
        )
    return results


# ============================================================
# GET /machines  (dulu /status-latest)
# ============================================================
@router.get("/")
def list_machines_latest():
    stmt = text("SELECT DISTINCT machine_id FROM sensor_readings")
    try:
        with _engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
    except Exception:
        raise HTTPException(500, "Database error fetching machines")

    machines = [r[0] for r in rows]
    out = []

    for m in machines:
        stmt2 = (
            select(
                _sensor_table.c.ts,
                _sensor_table.c.air_temperature,
                _sensor_table.c.process_temperature,
                _sensor_table.c.rotational_speed,
                _sensor_table.c.torque,
                _sensor_table.c.tool_wear,
                _sensor_table.c.metadata,
            )
            .where(_sensor_table.c.machine_id == m)
            .order_by(_sensor_table.c.ts.desc())
            .limit(1)
        )
        with _engine.connect() as conn:
            r = conn.execute(stmt2).fetchone()
        if not r:
            continue

        d = row_to_dict_safe(r)

        temp = d.get("air_temperature")
        vib = d.get("rotational_speed")
        current = d.get("torque")
        pressure = d.get("tool_wear")  # sementara kita pakai tool_wear sebagai "pressure"
        
        # pakai helper yang dibuat predictions.py
        risk = compute_risk(temp, vib, current)

    
        out.append({
            "machine_id": m,
            "ts": str(d.get("ts")),
            "temperature": temp,
            "vibration": vib,
            "current": current,
            "pressure": pressure,
            "risk": risk,
            "metadata": parse_metadata(d.get("metadata"))
        })

    return out


# ============================================================
# GET /machines/{machine_id}/aggregated
# ============================================================
_INTERVAL_RE = re.compile(r"^\s*\d+\s+(second|seconds|minute|minutes|hour|hours)\s*$", re.I)


@router.get("/{machine_id}/aggregated")
def aggregated(
    machine_id: str,
    from_ts: datetime = Query(..., alias="from"),
    to_ts: datetime = Query(..., alias="to"),
    interval: int = Query(60, description="interval in seconds"),
    limit: int = Query(200),
):
    if interval <= 0:
        raise HTTPException(400, "interval must be > 0")

    sql = text("""
        SELECT 
            to_timestamp(
                floor(extract(epoch FROM ts) / :interval) * :interval
            ) AT TIME ZONE 'UTC' AS bucket,
            AVG(air_temperature) AS avg_air_temp,
            MAX(air_temperature) AS max_air_temp,
            AVG(process_temperature) AS avg_process_temp,
            MAX(process_temperature) AS max_process_temp,
            AVG(torque) AS avg_torque,
            MAX(torque) AS max_torque,
            AVG(rotational_speed) AS avg_rot_speed,
            MAX(rotational_speed) AS max_rot_speed
        FROM sensor_readings
        WHERE machine_id = :mid
          AND ts BETWEEN :from_ts AND :to_ts
        GROUP BY bucket
        ORDER BY bucket DESC
        LIMIT :limit
    """)

    with _engine.connect() as conn:
        rows = conn.execute(sql, {
            "mid": machine_id,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "limit": limit,
            "interval": interval,
        }).fetchall()

    return [row_to_dict_safe(r) for r in rows]