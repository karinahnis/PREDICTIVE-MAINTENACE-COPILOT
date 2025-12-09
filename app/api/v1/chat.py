# backend/app/api/v1/chat.py

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.services.db_service import _engine, _sensor_table
from app.api.v1.predictions import compute_risk  # helper yang sudah kita buat

logger = logging.getLogger("chat")

router = APIRouter(prefix="/chat", tags=["chat"])


# =======================
# MODELS
# =======================

class ChatRequest(BaseModel):
    message: str
    machine_id: Optional[str] = None  # boleh kosong, boleh diisi M1/M2/M3


class ChatResponse(BaseModel):
    reply: str
    machine_id: Optional[str] = None
    intent: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


# =======================
# HELPERS
# =======================

def get_latest_machine_status(machine_id: str) -> Optional[Dict[str, Any]]:
    """Ambil 1 bacaan sensor terbaru untuk 1 mesin."""
    if _engine is None or _sensor_table is None:
        return None

    stmt = (
        select(
            _sensor_table.c.ts,
            _sensor_table.c.air_temperature,
            _sensor_table.c.process_temperature,
            _sensor_table.c.rotational_speed,
            _sensor_table.c.torque,
            _sensor_table.c.tool_wear,
        )
        .where(_sensor_table.c.machine_id == machine_id)
        .order_by(_sensor_table.c.ts.desc())
        .limit(1)
    )

    with _engine.connect() as conn:
        row = conn.execute(stmt).fetchone()

    if not row:
        return None

    d = dict(row._mapping)
    temp = d.get("air_temperature")
    vib = d.get("rotational_speed")
    current = d.get("torque")
    pressure = d.get("tool_wear")

    risk = compute_risk(temp, vib, current)

    return {
        "ts": str(d.get("ts")),
        "temperature": temp,
        "vibration": vib,
        "current": current,
        "pressure": pressure,
        "risk": risk,
    }


# =======================
# ENDPOINT: POST /chat/messages
# =======================

@router.post("/messages", response_model=ChatResponse)
def chat_messages(payload: ChatRequest):
    """
    Chatbot sederhana:
    - Kalau user tanya status mesin + machine_id → balas ringkasan kondisi.
    - Selain itu → balas template general.
    """
    text = payload.message.lower().strip()
    mid = payload.machine_id

    # Intent sederhana: cek kata kunci
    is_status_question = any(k in text for k in ["status", "kondisi", "keadaan", "bagaimana mesin"])
    is_risk_question = any(k in text for k in ["risiko", "resiko", "bahaya", "aman"])

    # Kalau user tanya status & ada machine_id
    if mid and (is_status_question or is_risk_question):
        status = get_latest_machine_status(mid)
        if status is None:
            return ChatResponse(
                reply=f"Saya belum menemukan data terbaru untuk mesin {mid}. Pastikan data sensor sudah terkirim.",
                machine_id=mid,
                intent="machine_status_not_found",
            )

        risk = status["risk"]
        temp = status["temperature"]
        vib = status["vibration"]
        current = status["current"]

        # Jawaban natural
        reply = (
            f"Kondisi terbaru mesin {mid}:\n"
            f"- Suhu: {temp:.2f} K\n"
            f"- Getaran (rpm): {vib}\n"
            f"- Arus/Torque: {current}\n"
            f"- Status risiko: {risk}.\n"
        )

        # Tambah rekomendasi sederhana
        if risk == "Bahaya":
            reply += "\nRekomendasi: Segera lakukan inspeksi menyeluruh dan hentikan operasi jika memungkinkan."
        elif risk == "Waspada":
            reply += "\nRekomendasi: Jadwalkan pengecekan dalam waktu dekat dan pantau tren sensor lebih sering."
        else:
            reply += "\nRekomendasi: Kondisi masih normal, tetap lakukan pemantauan berkala."

        return ChatResponse(
            reply=reply,
            machine_id=mid,
            intent="machine_status",
            extra=status,
        )

    # Default jawab umum (tidak spesifik mesin)
    default_reply = (
        "Halo, saya predictive maintenance copilot.\n\n"
        "Kamu bisa tanya hal-hal seperti:\n"
        "- 'Bagaimana status mesin M1?'\n"
        "- 'Apakah mesin M2 berisiko tinggi?'\n"
        "- 'Tolong jelaskan kondisi mesin M3 sekarang.'\n\n"
        "Jika perlu, sertakan juga ID mesin (misalnya: M1, M2, M3)."
    )

    return ChatResponse(
        reply=default_reply,
        machine_id=mid,
        intent="help",
    )
