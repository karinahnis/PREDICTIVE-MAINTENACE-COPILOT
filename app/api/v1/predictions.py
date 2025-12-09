import json
import os
import logging
from typing import List
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, text

from app.services.db_service import _engine, _sensor_table, _predictions_table
from app.api.v1.machine_utils import (
    PredictionResult,
    row_to_dict_safe,
    parse_metadata,
    parse_timestamp,
    call_ml_service_with_retry,
    score_to_label,
)

router = APIRouter(tags=["predictions"])
logger = logging.getLogger("predictions")

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml_service:5000/predict")

def compute_risk(
    temp_k: Optional[float],
    vib: Optional[float],
    current: Optional[float],
) -> str:
    """
    Hitung level risiko berbasis sensor terakhir.

    temp_k  : air_temperature (Kelvin)
    vib     : rotational_speed
    current : torque
    """
    if temp_k is None and vib is None and current is None:
        return "Unknown"

    # --- Bahaya ---
    if (temp_k is not None and temp_k > 315) or \
       (vib is not None and vib > 2200) or \
       (current is not None and current > 85):
        return "Bahaya"

    # --- Waspada ---
    if (temp_k is not None and temp_k > 305) or \
       (vib is not None and vib > 1600) or \
       (current is not None and current > 65):
        return "Waspada"

    # --- Normal ---
    return "Normal"


# ============================================================
# POST /machines/{machine_id}/predict
# ============================================================
@router.post("/machines/{machine_id}/predict", response_model=PredictionResult)
async def predict(machine_id: str, limit: int = Query(50, gt=1, le=2000), threshold: float = 0.7):
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
        )
        .where(_sensor_table.c.machine_id == machine_id)
        .order_by(_sensor_table.c.ts.desc())
        .limit(limit)
    )

    with _engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    if not rows:
        raise HTTPException(404, "No readings found for this machine.")

    readings = []
    latest_sensor_id = None
    latest_ts = None
    for r in rows:
        d = row_to_dict_safe(r)
        if latest_sensor_id is None:
            latest_sensor_id = d.get("id")
            latest_ts = d.get("ts")
        readings.append({
            "ts": (parse_timestamp(d["ts"]).isoformat() if d.get("ts") else None),
            "air_temperature": d.get("air_temperature"),
            "process_temperature": d.get("process_temperature"),
            "rotational_speed": d.get("rotational_speed"),
            "torque": d.get("torque"),
            "tool_wear": d.get("tool_wear"),
            "metadata": parse_metadata(d.get("metadata")),
        })

    payload = {"machine_id": machine_id, "readings": readings}

    try:
        ml = await call_ml_service_with_retry(ML_SERVICE_URL, payload)
    except Exception as e:
        raise HTTPException(502, f"ML service error: {e}")

    failure_prob = None
    prediction_label = None
    model_version = None
    raw_scores = None
    raw_features = None
    meta = None

    if isinstance(ml, dict):
        failure_prob = ml.get("failure_probability") or ml.get("score")
        prediction_label = ml.get("prediction_label") or ml.get("label")
        model_version = ml.get("model_version") or ml.get("model_name")
        raw_scores = ml.get("raw_scores") or ml.get("scores") or ml.get("probabilities")
        raw_features = ml.get("raw_features") or ml.get("features")
        meta = ml.get("meta", ml.get("explain", {}))
    else:
        meta = {"raw_ml_response": ml}

    try:
        failure_prob = float(failure_prob) if failure_prob is not None else None
    except Exception:
        failure_prob = None

    label_to_store = prediction_label if prediction_label is not None else score_to_label(failure_prob or 0.0)

    insert_sql = text("""
        INSERT INTO predictions(
            sensor_reading_id,
            machine_id,
            model_version,
            prediction_label,
            failure_probability,
            raw_scores,
            raw_features,
            metadata
        ) VALUES (
            :sensor_reading_id,
            :machine_id,
            :model_version,
            :prediction_label,
            :failure_probability,
            CAST(:raw_scores AS jsonb),
            CAST(:raw_features AS jsonb),
            CAST(:metadata AS jsonb)
        )
        RETURNING id
    """)

    raw_scores_json = json.dumps(raw_scores) if raw_scores is not None else "{}"
    raw_features_json = json.dumps(raw_features) if raw_features is not None else "{}"
    meta_json = json.dumps(meta) if meta is not None else "{}"

    params = {
        "sensor_reading_id": latest_sensor_id,
        "machine_id": machine_id,
        "model_version": model_version,
        "prediction_label": label_to_store,
        "failure_probability": failure_prob,
        "raw_scores": raw_scores_json,
        "raw_features": raw_features_json,
        "metadata": meta_json,
    }

    with _engine.begin() as conn:
        prediction_id = conn.execute(insert_sql, params).scalar()

    return PredictionResult(
        prediction_id=str(prediction_id),
        model_name=model_version,
        label=label_to_store,
        score=failure_prob,
        meta=meta,
    )


# ============================================================
# GET /machines/{machine_id}/prediction-history
# ============================================================
@router.get("/machines/{machine_id}/prediction-history", response_model=List[PredictionResult])
def history(machine_id: str, limit: int = Query(50, gt=1, le=2000)):
    stmt = (
        select(
            _predictions_table.c.id,
            _predictions_table.c.model_version,
            _predictions_table.c.failure_probability,
            _predictions_table.c.prediction_label,
            _predictions_table.c.metadata,
        )
        .where(_predictions_table.c.machine_id == machine_id)
        .order_by(_predictions_table.c.ts.desc())
        .limit(limit)
    )

    with _engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    out: List[PredictionResult] = []
    for r in rows:
        d = row_to_dict_safe(r)
        out.append(
            PredictionResult(
                prediction_id=str(d["id"]),
                model_name=d.get("model_version"),
                label=d.get("prediction_label"),
                score=float(d.get("failure_probability") or 0),
                meta=parse_metadata(d.get("metadata")),
            )
        )
    return out


# ============================================================
# GET /dashboard/summary  (pengganti health-overview)
# ============================================================
@router.get("/dashboard/summary")
def dashboard_summary():
    stmt = text("SELECT DISTINCT machine_id FROM sensor_readings")
    try:
        with _engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
    except Exception:
        raise HTTPException(500, "Database error fetching machines")

    machines = [r[0] for r in rows]
    counts = {
        "total": len(machines), 
        "failure_count": 0, 
        "warning_count": 0, 
        "normal_count": 0
    }

    for m in machines:
        stmt2 = (
            select(
                _sensor_table.c.air_temperature,
                _sensor_table.c.rotational_speed,
                _sensor_table.c.torque,
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
        temp = d.get("air_temperature") or 0
        vib = d.get("rotational_speed") or 0
        current = d.get("torque") or 0

        risk = compute_risk(temp, vib, current)

        if risk == "Bahaya":
            counts["failure_count"] += 1
        elif risk == "Waspada":
            counts["warning_count"] += 1
        else:
            counts["normal_count"] += 1

    return counts
