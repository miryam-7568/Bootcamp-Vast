# Orthophoto Canvas (PyQt)

A lightweight orthophoto viewer built with PyQt5 and `QGraphicsView`.
It reads a standard tile pyramid (folders `z/x/y.png`) in XYZ or TMS layout, lazily loads only what’s visible, and snaps to “native” scales to keep imagery crisp (no blur).

## Features

* **Lazy tile loading**: loads only the tiles that enter the viewport.
* **LOD (level-of-detail)**: picks the logical zoom `z` based on tile size on screen.
* **XYZ/TMS auto-detection**: flips Y when needed.
* **Snap to native scale**: avoids smoothing/resampling blur.
* **Smooth navigation**: wheel zoom, drag to pan, handy hotkeys.
* **Smart initial focus**: centers on real data and fits width (tunable).

---

## Requirements

* Windows / macOS / Linux
* Python 3.10–3.12
* Packages: `PyQt5` (and optionally `Pillow` if you extend I/O)

Use a virtual environment for a clean install.

---

## Quick Start

From `orthophoto_canvas` folder:

```powershell
# create & activate venv (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\activate

# install dependencies
python -m pip install --upgrade pip
pip install PyQt5
```

> **Important:** Always run with the same Python interpreter as your venv.
> If you see a “Qt platform plugin ‘windows’” error, it usually means you launched with a different Python than the one that has PyQt5 installed.

---

## Run

With your venv active, run:

```powershell
python -m orthophoto_canvas --tiles .\data\tiles
```

or provide an absolute path:

```powershell
python -m orthophoto_canvas --tiles C:\path\to\tiles
```

`--tiles` must point to the **root** folder that contains subfolders named by `z` (zoom levels), and under each `z` folders named by `x`, and inside each, images named `y.png`/`.jpg`.

---

## Where do tiles come from?

If you start with a GeoTIFF, create a web-mercator tile pyramid:

1. Reproject to **EPSG:3857** (if needed):

```powershell
gdalwarp -t_srs EPSG:3857 input.tif output_3857.tif
```

2. Cut to tiles (example: 512×512, XYZ, zooms 10–18):

```powershell
python -m osgeo_utils.gdal2tiles --xyz -z 10-18 --tilesize 512 -r cubic `
  output_3857.tif C:\path\to\tiles
```

Folder layout example:

```
tiles/
  10/
    611/
      391000.png
      ...
  ...
  18/
    156448/
      250368.png
      ...
```

The viewer auto-detects XYZ vs TMS (Y-flip) — no manual switch required.

---

## Keyboard & Navigation

* **Mouse wheel**: zoom in/out around the cursor.
* **Drag (left mouse)**: pan.
* **1 … 5**: jump to preset tile sizes on screen (from far to near).
* **C**: snap to nearest **native** scale (sharp, no blur).
* **F**: fit the whole scene width (general).
* **W**: fit **data** width (only the data extent, not empty scene space).
* **G**: re-focus to a known data tile if you “lost” the imagery.

By default, on first show the viewer does `fit_to_data("width", 0.98)`.
If you want to open **larger/closer**, add a scale multiplier afterward (see below).

---

## Control the initial zoom

In `ui/viewer.py`, after the initial fit you can add a scale bump:

```python
from PyQt5.QtCore import QTimer

# inside __init__ or showEvent, after indexing is ready:
QTimer.singleShot(0, lambda: (self.fit_to_data("width", 0.98), self.scale(1.25, 1.25)))
```

* Increase `1.25` to open even closer.
* Or reduce the margin (e.g. `0.92`) to use more of the window width.

---

## Project Layout

```
orthophoto_canvas/
  __init__.py
  __main__.py      # enables: python -m orthophoto_canvas
  app.py           # CLI entry: parse args, create QApplication, show Viewer
  ui/
    __init__.py
    viewer.py      # OrthophotoViewer: LOD, lazy loading, crisp placement, input
  utils/
    __init__.py
    tiles.py       # TileStore: scan z/x/y, ranges, XYZ/TMS detection, file helpers
  data/
    tiles/         # example tiles (optional), or place your own path & pass --tiles
  scripts/         # optional scripts (tiling, tests)
  geo/             # optional GIS helpers (future)
  ag_io/           # optional I/O modules (future)
  README.md
```

* **`app.py`**
  Parses `--tiles`, builds `QApplication`, constructs `OrthophotoViewer` with the tiles path, and shows the window.

* **`ui/viewer.py`**
  The full viewer: indexing (scan zooms/ranges), scene anchoring, LOD decision, placeholder → pixmap upgrades, crisp placement/scaling, input handlers, hotkeys, initial fit.

* **`utils/tiles.py`**
  `TileStore`: fast scanning of `z` folders, min/max `x,y` per `z`, robust XYZ/TMS pathing, and helpers for “first real tile” / nearest tiles.

---

## Troubleshooting

**Error**
`qt.qpa.plugin: Could not find the Qt platform plugin "windows" in ""`

**Fix**

* Make sure you’re running the venv’s Python:

  ```powershell
  .\.venv\Scripts\python.exe -m orthophoto_canvas --tiles .\data\tiles
  ```
* If still failing:

  ```powershell
  pip uninstall -y PyQt5
  pip install PyQt5
  ```

**Error**
`AttributeError: 'OrthophotoViewer' object has no attribute 'x_min'`

**Cause**
A view/fit call happened before indexing finished (zoom ranges/anchors not set).

**Fix**
Ensure indexing runs first (the shipped code guards this). When adding custom init code, call your fits only after the scene bounds and zoom ranges are available (the default `showEvent` path with `QTimer.singleShot` already does that).

---

## Optional Extensions

* **Sensor overlay (CSV)**
  Add a simple CSV (`lon,lat,label`) loader, transform to EPSG:3857, and draw small markers on the map. (You can wire a `--sensors` flag in `app.py` and pass to the viewer.)

* **Pixmap cache**
  For large datasets, consider caching QPixmaps to reduce disk hits.

---

## License

MIT (or your project’s license).

---

## Credits

Built as an internal viewer for AgCloud with a focus on simplicity, performance, and crisp rendering.
