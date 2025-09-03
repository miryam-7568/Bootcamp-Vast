from __future__ import annotations
import os
import uuid
import typing as t

try:
    import requests
except Exception as e:  
    raise RuntimeError("Please install 'requests' (pip install requests)") from e

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")

def get_sensors() -> list[dict]:
    """
    reads the list of sensors from the gateway according to the DSL you provided.
    returns list[dict] with keys like: sensor_id, lat, lon, status, name, label, battery, moisture.
    """
    plan = {
        "source": "sensors",
        "_ops": [
            {"op": "select", "columns": [
                "sensor_id","lat","lon","status","name","label","battery","moisture"
            ]},
            {"op": "where", "cond": {
                "any": [
                    {"op": "=", "left": {"col": "status"}, "right": {"literal": "ok"}},
                    {"op": "=", "left": {"col": "status"}, "right": {"literal": "warning"}}
                ]
            }}
        ]
    }
    headers = {
        "Content-Type": "application/json",
        "X-Request-Id": str(uuid.uuid4()),
    }
    try:
        resp = requests.post(f"{GATEWAY_URL}/runQuery", json=plan, headers=headers, timeout=30)
        resp.raise_for_status()
        data: t.Any = resp.json()
    except requests.exceptions.ConnectionError:
        print("WARNING: Could not connect to sensors API! Returning empty list.")
        data: t.Any = []
    except Exception as e:
        print(f"ERROR: Failed to fetch sensors: {e}")
        data: t.Any = []
    # gentle validation + filtering
    out: list[dict] = []
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except Exception:
                continue
            out.append(row)
    return out

# def get_sensors() -> list[dict]:
    # """
    # Returns a hardcoded list of fake sensors for testing the UI (instead of calling the API).
    # """
    # return [
    #     {
    #         "sensor_id": "A-101",
    #         "lat": 31.8998,
    #         "lon": 34.849524,
    #         "name": "Soil Probe A",
    #         "battery": "3.86V",
    #         "moisture": "21%",
    #         "status": "ok",
    #         "label": "Field Sensor"
    #     },
    #     {
    #         "sensor_id": "D-404",
    #         "lat": 31.8978,
    #         "lon": 34.849524,
    #         "name": "Soil Probe B",
    #         "battery": "3.86V",
    #         "moisture": "21%",
    #         "status": "ok",
    #         "label": "Greenhouse Sensor"
    #     },
    #     {
    #         "sensor_id": "E-505",
    #         "lat": 31.8978,
    #         "lon": 34.850924,
    #         "name": "Soil Probe C",
    #         "battery": "3.86V",
    #         "moisture": "19%",
    #         "status": "ok",
    #         "label": "Pump Room"
    #     },
    #     {
    #         "sensor_id": "B-202",
    #         "lat": 31.8996,
    #         "lon": 34.849524,
    #         "label": "Valve East 4",
    #         "battery": "3.55V",
    #         "status": "warning"
    #     },
    #     {
    #         "sensor_id": "C-303",
    #         "lat": 31.8999,
    #         "lon": 34.851734,
    #         "status": "offline",
    #         "label": "Weather Station"
    #     }
    # ]