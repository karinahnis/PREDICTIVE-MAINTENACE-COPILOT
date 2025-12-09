# create_tables.py
from sqlalchemy import create_engine
import os

from .models import Base  # sesuaikan path kalau perlu

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:12345@localhost:5432/predictive_maintenance_db"
)

engine = create_engine(DATABASE_URL, future=True)

if __name__ == "__main__":
    print("Creating tables from models.py ...")
    Base.metadata.create_all(bind=engine)
    print("Done!")
