# VAST Dashboard (PyQt6 + Grafana + Orthophoto + Sensors Gateway)

A desktop monitoring dashboard built with **PyQt6**. It combines three data layers on a single Home screen:

- **Grafana embeds (demo):** two Grafana panels rendered via QWebEngine (Prometheus demo data; not related to the map sensors).
- **Orthophoto map:** a fast tiled orthophoto viewer (QGraphicsView/QGraphicsScene) with smooth zoom & pan.
- **Live sensor overlay (real):** a DSL → SQL gateway backed by a gRPC runner querying a SQLite database and returning sensor rows that are plotted on the map.

## Components

- `src/vast/auth_ui/` – Login/Signup pages and a small in-memory auth service (app starts on Login; successful sign-in opens the main window; Logout returns to Login).
- `src/vast/orthophoto_canvas/` – Tiled viewer (`ui/viewer.py`), sensor overlay (`ui/sensors_layer.py`), data access (`ag_io/sensors_api.py`).
- `src/vast/dsl/` – A compact query DSL (JSON plan).
- `src/vast/runner/` – gRPC server executing SQL against SQLite (`data/app.db`).
- `src/vast/gateway/` – FastAPI app exposing `/runQuery`; translates DSL to SQL, calls the runner, and returns JSON.
- `src/vast/services/` – Flask utilities (Prometheus demo exporter, optional simple web map).
- `grafana/`, `prometheus/` – Dockerized Grafana/Prometheus for the demo panels.
- `src/vast/main.py`, `src/vast/main_window.py`, `src/vast/home_view.py` – Desktop shell (menu, navigation, and Home layout: Grafana on top, orthophoto below).

## Requirements

Install everything from the single unified requirements file at the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
```

```bash
pip install -r requirements.txt
```

> Desktop GUI deps (PyQt6 / WebEngine) are installed on **Windows and macOS** only (via environment markers):
>
> ```text
> PyQt6==6.9.1 ; platform_system == "Windows" or platform_system == "Darwin"
> PyQt6-WebEngine==6.9.0 ; platform_system == "Windows" or platform_system == "Darwin"
> ```
> Linux containers stay slim and avoid Qt/WebEngine system dependencies. If you develop the desktop app on Linux,
> install these two packages explicitly on your host: `pip install PyQt6 PyQt6-WebEngine`.

---

## Run with Docker (recommended)

Make sure build context is the **repo root** and Dockerfiles are referenced under `src/vast/...` in `docker-compose.yml`.

```yaml
services:
  runner:
    build:
      context: .
      dockerfile: src/vast/runner/Dockerfile
    environment:
      - RUNNER_MODE=real
      - SQLITE_DB=/data/app.db
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/data        # RW mount for SQLite
    ports:
      - "50051:50051"

  gateway:
    build:
      context: .
      dockerfile: src/vast/gateway/Dockerfile
    environment:
      - RUNNER_ADDR=runner:50051
    ports:
      - "9001:9001"

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ALLOW_EMBEDDING=true
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
      - GF_USERS_DEFAULT_THEME=light
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

Build and run:

```bash
docker compose build runner gateway
docker compose up -d runner gateway prometheus grafana
docker compose ps
```

Check services:
- Gateway API: `http://localhost:9001`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

---

## Run locally (without Docker)

Create and activate a venv, then run the services and desktop app in separate terminals.

# Start Grafana/Prometheus (optional but recommended for the demo)
```bash
docker compose up -d prometheus grafana
docker compose ps
```

### Terminal A – Runner (gRPC)
```bash
.\.venv\Scripts\Activate.ps1
# Change the path according to the current location of the project
$env:SQLITE_DB = "/C:/Users/sara/Documents/login-and-gui/data/app.db"
python -m vast.runner.runner_server
```

### Terminal B – Gateway (FastAPI)
```bash
python -m uvicorn vast.gateway.app:create_app --factory --host 127.0.0.1 --port 9001
```

### Terminal C – Demo metrics exporter (optional)
```bash
python -m vast.services.sensors_metrics_app
```

### Terminal D – Desktop app (PyQt6)
**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
$env:GATEWAY_URL = "http://127.0.0.1:9001"
python .\src\vast\main.py
```

**macOS/Linux (bash):**
```bash
source .venv/bin/activate
export GATEWAY_URL="http://127.0.0.1:9001"
python ./src/vast/main.py
```

> Note (Linux/macOS): you may need to install system Qt dependencies for PyQt6 (including WebEngine).

---

## Orthophoto Canvas (PyQt6)

A tiled orthophoto viewer built with QGraphicsView/QGraphicsScene. It loads only the tiles that enter the viewport, keeps imagery crisp by snapping to native scales, and provides smooth navigation.

### Features
- Lazy tile loading (only tiles in view are fetched)
- LOD (level-of-detail) with smart `z` selection
- XYZ/TMS auto-detection (flips Y when needed)
- Snap to native scale (crisp imagery, no blur)
- Smooth navigation: wheel to zoom, drag to pan
- Smart initial focus: fits to the real data extent

### Quick start (desktop app)

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
$env:GATEWAY_URL = "http://127.0.0.1:9001"
python .\src\vast\main.py
```

**macOS/Linux (bash):**
```bash
source .venv/bin/activate
export GATEWAY_URL="http://127.0.0.1:9001"
python ./src/vast/main.py
```

> Note (Linux/macOS): you may need to install system Qt dependencies for PyQt6 (including WebEngine).

### Tile data layout (XYZ/TMS)
```text
tiles/
  {z}/
    {x}/
      {y}.png
```

### Hotkeys
- **Wheel**: zoom in/out
- **Drag**: pan
- **Shift + Wheel**: slow, precise zoom
- **F**: fit to data extent
- **W**: fit width (data extent)
- **G**: refocus to a known data tile


## Environment variables

- `RUNNER_MODE` (runner): `real` or simulation mode (if implemented).
- `SQLITE_DB`   (runner): path to SQLite DB (default `/data/app.db`).
- `LOG_LEVEL`   (both):   `INFO`, `DEBUG`, etc.
- `RUNNER_ADDR` (gateway): gRPC target, e.g. `runner:50051`.
- `GATEWAY_URL` (desktop): HTTP endpoint for the gateway, e.g. `http://127.0.0.1:9001`.

---

## Notes

- Keep Docker `build.context` at repo root so `requirements.txt`, `certs/`, `proto/` and source folders are visible to the build.
- If SQLite errors occur inside containers, ensure `./data` is mounted **RW** (no `:ro`) so WAL/journal files can be created.
- The `version:` key in `docker-compose.yml` is obsolete and can be removed.

## Prerequisites

- **Windows + PowerShell**
- **Python 3.12**
- **pip** (latest), **wheel**
- **Docker Desktop** (for Grafana/Prometheus demo)
- **Git**

---

## Setup

```powershell
# From the repository root
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip wheel

# Install all project deps (top-level + module-specific)
pip install -r .\requirements.txt `

# Ensure binary wheels for these heavy packages (avoids build issues)
pip install --only-binary=:all: PyQt6 PyQt6-WebEngine grpcio grpcio-tools


## Running (4 terminals)
#Start Grafana/Prometheus (optional but recommended for the demo
docker compose up -d prometheus grafana
docker compose ps

## Terminal A - Runner (gRPC → SQLite)
.\.venv\Scripts\Activate.ps1
$env:SQLITE_DB = "/C:/Users/sara/Documents/login-and-gui/data/app.db"
python -m vast.runner.runner_server

## Terminal B – Gateway (FastAPI)
.\.venv\Scripts\Activate.ps1
python -m uvicorn vast.gateway.app:create_app --factory --host 127.0.0.1 --port 9001

## Terminal C - Demo metrics exporter (Flask)
.\.venv\Scripts\Activate.ps1
python -m vast.services.sensors_metrics_app

## Terminal D - Desktop app (PyQt6)
.\.venv\Scripts\Activate.ps1
$env:GATEWAY_URL = "http://127.0.0.1:9001"
python .\src\vast\main.py

