# app/api/v1/schemas.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# ==== Dashboard ====
class DashboardSummary(BaseModel):
    total_machines: int
    normal_count: int
    warning_count: int
    failure_count: int


class MachineStatus(BaseModel):
    machine_id: str
    name: Optional[str]
    location: Optional[str]
    status: str              # normal | warning | failure
    health_score: float      # 0-100
    failure_prob: float      # 0-1
    last_update: datetime


# ==== Timeseries ====
class TimePoint(BaseModel):
    time: datetime
    air_temperature: Optional[float] = None
    process_temperature: Optional[float] = None
    rotational_speed: Optional[float] = None
    torque: Optional[float] = None
    tool_wear: Optional[float] = None


class TimeSeriesResponse(BaseModel):
    machine_id: str
    points: List[TimePoint]
