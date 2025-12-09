from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import random

app = FastAPI(title="ML Mock Service")

class Reading(BaseModel):
    ts: str
    air_temperature: Optional[float] = None
    process_temperature: Optional[float] = None
    rotational_speed: Optional[int] = None
    torque: Optional[float] = None
    tool_wear: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class PredictPayload(BaseModel):
    machine_id: str
    readings: List[Reading]

@app.post("/predict")
def predict(payload: PredictPayload):

    # Ambil nilai dari data terbaru
    last = payload.readings[0]

    # Mock scoring
    score = random.uniform(0, 1)

    # Mock label
    if score > 0.7:
        label = "failure"
    elif score > 0.3:
        label = "warning"
    else:
        label = "normal"

    return {
        "model_version": "mock-v1",
        "failure_probability": score,
        "prediction_label": label,
        "raw_scores": {"p": score},
        "raw_features": {"temp": last.air_temperature},
        "meta": {"mock": True}
    }
