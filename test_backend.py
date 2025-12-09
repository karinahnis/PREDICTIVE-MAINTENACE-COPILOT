# test_backend.py
import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000/api/v1"
MACHINE_ID = "machine_01"

# Step 1: Ingest sensor readings
print("=" * 60)
print("STEP 1: Ingesting sensor readings...")
print("=" * 60)

ingest_payloads = [
    {
        "machine_id": MACHINE_ID,
        "time": datetime.now().isoformat(),
        "air_temperature": 305.5,
        "process_temperature": 310.2,
        "rotational_speed": 1500,
        "torque": 45.2,
        "tool_wear": 120,
        "metadata": {"location": "factory_A"}
    },
    {
        "machine_id": MACHINE_ID,
        "time": datetime.now().isoformat(),
        "air_temperature": 308.1,
        "process_temperature": 312.5,
        "rotational_speed": 1600,
        "torque": 48.5,
        "tool_wear": 125,
        "metadata": {"location": "factory_A"}
    },
    {
        "machine_id": MACHINE_ID,
        "time": datetime.now().isoformat(),
        "air_temperature": 310.0,
        "process_temperature": 315.0,
        "rotational_speed": 1800,
        "torque": 52.1,
        "tool_wear": 130,
        "metadata": {"location": "factory_A"}
    }
]

for i, payload in enumerate(ingest_payloads):
    url = f"{BASE_URL}/ingest"
    print(f"\nIngesting reading {i+1}...")
    r = requests.post(url, json=payload, timeout=10)
    print(f"STATUS: {r.status_code}")
    print(f"RESPONSE: {json.dumps(r.json(), indent=2)}")

# Step 2: Predict on the ingested machine
print("\n" + "=" * 60)
print("STEP 2: Making prediction on ingested data...")
print("=" * 60)

url = f"{BASE_URL}/machines/{MACHINE_ID}/predict"
print(f"\nSENDING to {url}")
r = requests.post(url, timeout=30)
print(f"STATUS: {r.status_code}")
try:
    print(f"BODY JSON: {json.dumps(r.json(), indent=2)}")
except Exception:
    print(f"BODY TEXT: {r.text}")

# Step 3: Get recent readings with predictions
print("\n" + "=" * 60)
print("STEP 3: Fetching recent readings with predictions...")
print("=" * 60)

url = f"{BASE_URL}/machines/{MACHINE_ID}/recent?limit=10"
print(f"\nSENDING to {url}")
r = requests.get(url, timeout=10)
print(f"STATUS: {r.status_code}")
try:
    print(f"BODY JSON: {json.dumps(r.json(), indent=2)}")
except Exception:
    print(f"BODY TEXT: {r.text}")
