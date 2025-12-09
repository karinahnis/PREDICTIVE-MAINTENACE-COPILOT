# backend/app/api/v1/ingest.py
from fastapi import APIRouter, Header, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.core.config import get_settings
from app.services import db_service
import logging

router = APIRouter()
settings = get_settings()
LOGGER = logging.getLogger("ingest")


# ------------------- MODELS -------------------
class Metadata(BaseModel):
    sensor_version: Optional[str] = None
    notes: Optional[str] = None


class IngestPayload(BaseModel):
    machine_id: str
    time: datetime

    air_temperature: float
    process_temperature: float
    rotational_speed: int
    torque: float
    tool_wear: int

    metadata: Optional[Dict[str, Any]] = None


class IngestRecord(BaseModel):
    id: int
    machine_id: str
    ts: datetime

    air_temperature: float
    process_temperature: float
    rotational_speed: int
    torque: float
    tool_wear: int

    metadata: Optional[Dict[str, Any]]


# ------------------- POST /ingest -------------------
@router.post("/ingest", status_code=200)
def ingest(payload: IngestPayload, x_api_key: Optional[str] = Header(None)):
    """
    Ingest endpoint for sensor data.
    """
    # optional: validate API key
    # if x_api_key != settings.INGEST_API_KEY:
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    data = payload.dict()
    try:
        inserted_id = db_service.insert_reading(data)
        return {"status": "ok", "id": inserted_id}
    except Exception:
        LOGGER.exception("Ingest failed")
        raise HTTPException(status_code=500, detail="Ingest failed")


# ------------------- GET /ingest -------------------
@router.get("/ingest", response_model=List[IngestRecord])
def get_ingest(
    machine_id: Optional[str] = Query(None),
    limit: int = Query(100, gt=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """
    Fetch ingested sensor data from DB.

    - GET /ingest → returns last 100 rows
    - GET /ingest?machine_id=M123 → filter by machine
    - Supports pagination with limit & offset
    """
    try:
        rows = db_service.fetch_readings(
            machine_id=machine_id,
            limit=limit,
            offset=offset,
        )
        return rows

    except Exception:
        LOGGER.exception("Failed to fetch ingest data")
        raise HTTPException(status_code=500, detail="Failed to fetch ingest data")
