# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from app.api.v1.ingest import router as ingest_router
from app.api.v1.machines import router as machines_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.chat import router as chat_router
# nanti kalau sudah ada:
# from app.api.v1.chat import router as chat_router
# from app.api.v1.tickets import router as tickets_router

app = FastAPI(title="Predictive Maintenance Backend (dev)")

# CORS untuk development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # untuk production sebaiknya diganti domain FE saja
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api/v1
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(machines_router, prefix="/api/v1")
app.include_router(predictions_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1") 
# app.include_router(chat_router, prefix="/api/v1")
# app.include_router(tickets_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Predictive Maintenance Backend API"}
