import asyncio
import datetime
import json
import logging
from typing import Optional, Any, Dict

import httpx
from pydantic import BaseModel

logger = logging.getLogger("machine_utils")

# ============================================================
# Pydantic models yang dipakai di banyak router
# ============================================================
class PredictionResult(BaseModel):
    model_config = {
        "protected_namespaces": (),
    }
    
    prediction_id: str
    model_name: Optional[str]
    label: Optional[str]
    score: Optional[float]
    meta: Optional[dict]


# ============================================================
# Konstanta & helper umum
# ============================================================
LABEL_MAP = {0: "normal", 1: "warning", 2: "failure"}


def score_to_label(score: float) -> str:
    return "normal" if score < 0.3 else "warning" if score < 0.7 else "failure"


async def call_ml_service_with_retry(url, payload, retries=5, backoff=0.5):
    last_error = None
    async with httpx.AsyncClient(timeout=15.0) as client:
        for i in range(retries):
            try:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_error = e
                await asyncio.sleep(backoff * (2 ** i))
    raise last_error


def row_to_dict_safe(r):
    if r is None:
        return None
    if isinstance(r, dict):
        return r
    mapping = getattr(r, "_mapping", None)
    if mapping:
        return dict(mapping)
    raise TypeError("Unknown row type for conversion")


def parse_metadata(raw):
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return None


def parse_timestamp(ts):
    if isinstance(ts, datetime.datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
    return None
