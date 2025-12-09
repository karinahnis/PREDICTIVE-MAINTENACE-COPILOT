# app/db/models.py
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Float,
    JSON,
    TIMESTAMP,
    Text,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    machine_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200))
    location = Column(String(200))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    time = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    machine_id = Column(String(50), nullable=False, index=True)
    air_temperature = Column(Float)
    process_temperature = Column(Float)
    rotational_speed = Column(Float)
    torque = Column(Float)
    tool_wear = Column(Float)
    raw_json = Column(JSON)
    # created_at ada di SQL, boleh kamu tambahkan juga kalau mau.


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    time = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)
    machine_id = Column(String(50), nullable=False, index=True)
    window_n = Column(Integer)
    probability = Column(Float)
    failure_type = Column(String(100))
    failure_name = Column(String(200))
    explanation = Column(Text)
    model_version = Column(String(100))
    raw_input = Column(JSON)
    raw_output = Column(JSON)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    machine_id = Column(String(50), nullable=False, index=True)
    created_by = Column(String(100))
    severity = Column(String(20))
    status = Column(String(20), default="open")
    message = Column(Text)
    probability = Column(Float)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    resolved_at = Column(TIMESTAMP(timezone=True))
    