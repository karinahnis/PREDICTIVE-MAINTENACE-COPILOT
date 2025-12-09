# config.py
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Pydantic V2 configuration
    model_config = {
        "protected_namespaces": (),
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    # DB
    DB_HOST: str = Field("localhost", env="DB_HOST")
    DB_PORT: int = Field(5432, env="DB_PORT")
    DB_NAME: str = Field("pm_db", env="DB_NAME")
    DB_USER: str = Field("pm_user", env="DB_USER")
    DB_PASS: str = Field("pm_pass", env="DB_PASS")

    DATABASE_URL: Optional[str] = Field(None, env="DATABASE_URL")

    # ML service URL 
    ML_SERVICE_URL: str = Field("http://localhost:9000/predict", env="ML_SERVICE_URL")

    # Ingest API key for streamer (we'll tell Ica)
    INGEST_API_KEY: str = Field(default="dev123")

    # Ticket threshold
    TICKET_THRESHOLD: float = Field(0.7, env="TICKET_THRESHOLD")

    # OpenAI key for chatbot
    OPENAI_API_KEY: str = Field(None, env="OPENAI_API_KEY")

    # App
    APP_HOST: str = Field("0.0.0.0", env="APP_HOST")
    APP_PORT: int = Field(8000, env="APP_PORT")



@lru_cache()
def get_settings():
    return Settings()
