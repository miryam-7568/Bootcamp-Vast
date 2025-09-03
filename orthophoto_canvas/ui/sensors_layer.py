from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any, List, TYPE_CHECKING
import math
from PyQt5.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsSimpleTextItem, QGraphicsItem,
    QGraphicsPathItem, QGraphicsTextItem, QToolTip
)
from PyQt5.QtGui import QBrush, QPen, QColor, QPainterPath, QLinearGradient, QFont
from PyQt5.QtCore import Qt, QPointF

TILE_SIZE = 512
MERCATOR_MAX_LAT = 85.05112878

KNOWN_SPEC_KEYS = frozenset({"label", "color", "radius_px", "min_z", "max_z", "hover"})
ID_KEYS  = ("sensor_id", "id", "sensorId")
LAT_KEYS = ("lat", "latitude")
LON_KEYS = ("lon", "lng", "longitude")

@dataclass
class SensorSpec:
    sensor_id: str
    label: str = ""
    color: QColor = field(default_factory=lambda: QColor(0, 120, 255))
    radius_px: float = 8.0
    min_z: Optional[int] = None
    max_z: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    # Mode 1 (base coords)
    xb: Optional[float] = None
    yb: Optional[float] = None
    # Mode 2 (tile + pixel offset)
    z: Optional[int] = None
    x: Optional[int] = None
    y: Optional[int] = None
    offset_px: Tuple[float, float] = (TILE_SIZE / 2.0, TILE_SIZE / 2.0)

class _HoverPopup:
    def __init__(self, scene):
        self._bg = QGraphicsPathItem()
        self._bg.setZValue(1_000_000_000)
        self._bg.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        
        self._radius = 10.0
        self._pad_w, self._pad_h = 18, 16
        self._border_pen = QPen(QColor(0, 0, 0, 40), 1)
        
        self._text = QGraphicsTextItem(self._bg)
        self._text.setDefaultTextColor(QColor(24, 24, 24))
        self._text.setZValue(1_000_000_001)
        self._text.setPos(14, 12)
        self._text.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        
        scene.addItem(self._bg)
        self._bg.setVisible(False)
        self._for_sensor_id = None

    def _update_bg_path(self, w: float, h: float, accent: QColor):
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, self._radius, self._radius)
        path.moveTo(26.0, h); path.lineTo(34.0, h + 10.0); path.lineTo(42.0, h); path.closeSubpath()
        self._bg.setPath(path)

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(255, 255, 255, 250))
        grad.setColorAt(1.0, QColor(245, 247, 250, 240))
        self._bg.setBrush(QBrush(grad))
        self._bg.setPen(self._border_pen)

    def show_for(self, sensor_id: str, html: str, anchor_scene_pos: QPointF, accent: Optional[QColor] = None):
        self._for_sensor_id = sensor_id
        self._text.setHtml(html or f"<b>{sensor_id}</b>")
        br = self._text.boundingRect()
        w = max(br.width() + self._pad_w + 16, 320.0)
        h = max(br.height() + self._pad_h + 20, 140.0)
        self._update_bg_path(w, h, accent or QColor(0, 120, 255))
        
        sr = self._bg.scene().sceneRect()
        desired_x = anchor_scene_pos.x() + 16
        desired_y = anchor_scene_pos.y() - (h + 18)
        x = min(max(sr.left() + 4, desired_x),  sr.right()  - w - 4)
        y = min(max(sr.top()  + 4, desired_y),  sr.bottom() - h - 4)
        self._bg.setPos(QPointF(x, y))
        self._bg.setVisible(True)
        self._bg.update()

    def hide_if_for(self, sensor_id: Optional[str] = None):
        if sensor_id is None or sensor_id == self._for_sensor_id:
            self._bg.setVisible(False)
            self._for_sensor_id = None

    def visible_for(self) -> Optional[str]:
        return self._for_sensor_id

class _SensorDot(QGraphicsEllipseItem):
    def __init__(self, layer_ref, spec, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._layer = layer_ref
        self._spec = spec
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        self._layer._on_sensor_hover_enter(self, self._spec)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._layer._on_sensor_hover_leave(self, self._spec)
        super().hoverLeaveEvent(event)

class SensorLayer:
    """
    Draws interactive sensor dots with hover popups and labels.
    """
    def __init__(self, viewer):
        self.viewer = viewer
        self._items: Dict[str, Tuple[QGraphicsEllipseItem, Optional[QGraphicsSimpleTextItem], SensorSpec]] = {}
        self._popup = _HoverPopup(self.viewer.scene)
        self.viewer.update_timer.timeout.connect(self._on_view_update)

    def specs(self):
        return [tpl[2] for tpl in self._items.values()]

    def add_sensor(self, spec: SensorSpec):
        if spec.sensor_id in self._items:
            self.remove_sensor(spec.sensor_id)

        sx, sy = self._sensor_scene_pos(spec)
        print(f"add_sensor: sensor_id={spec.sensor_id}, radius_px={spec.radius_px}, sx={sx}, sy={sy}")
        r = float(spec.radius_px)
        dot = _SensorDot(self, spec, -r, -r, 2.0 * r, 2.0 * r)
        dot.setBrush(QBrush(spec.color))
        dot.setPen(QPen(Qt.NoPen))
        dot.setPos(QPointF(sx, sy))
        dot.setZValue(1_000_000)

        self.viewer.scene.addItem(dot)
        self._items[spec.sensor_id] = (dot, None, spec)
        self._apply_visibility_for_current_zoom(spec.sensor_id)

    def add_sensors(self, specs: List[SensorSpec]):
        for s in specs:
            self.add_sensor(s)

    def remove_sensor(self, sensor_id: str):
        tpl = self._items.pop(sensor_id, None)
        if not tpl:
            return
        self._popup.hide_if_for(sensor_id)
        dot, label_item, _ = tpl
        if label_item: self.viewer.scene.removeItem(label_item)
        self.viewer.scene.removeItem(dot)

    def clear(self):
        for sid in list(self._items.keys()):
            self.remove_sensor(sid)

    # Hover popup

    def _on_sensor_hover_enter(self, dot_item: QGraphicsEllipseItem, spec: SensorSpec):
        html = self._format_popup_html(spec)
        view = self.viewer
        gp = view.mapToGlobal(view.mapFromScene(dot_item.scenePos()))
        QToolTip.showText(gp, html)

    def _on_sensor_hover_leave(self, _dot_item: QGraphicsEllipseItem, spec: SensorSpec):
        self._popup.hide_if_for(spec.sensor_id)

    # placement

    def _sensor_scene_pos(self, spec: SensorSpec) -> Tuple[float, float]:
        v = self.viewer
        if spec.xb is not None and spec.yb is not None:
            return (spec.xb - v.ts.z_ranges[v.min_zoom_fs][0]) * TILE_SIZE, (spec.yb - v.ts.z_ranges[v.min_zoom_fs][2]) * TILE_SIZE
        if spec.z is not None and spec.x is not None and spec.y is not None:
            eff_scene = TILE_SIZE / float(1 << (spec.z - v.min_zoom_fs))
            sx, sy, _ = v._tile_scene_pos(spec.z, spec.x, spec.y, eff_scene)
            dx, dy = spec.offset_px
            return sx + float(dx) * (eff_scene / TILE_SIZE), sy + float(dy) * (eff_scene / TILE_SIZE)
        raise ValueError(f"SensorSpec {spec.sensor_id}: provide either (xb,yb) or (z,x,y[+offset_px])")

    def _on_view_update(self):
        for sid in list(self._items.keys()):
            self._apply_visibility_for_current_zoom(sid)
        vis_for = self._popup.visible_for()
        if vis_for is not None:
            tpl = self._items.get(vis_for)
            if tpl:
                _, _, spec = tpl
                z_now = self.viewer._calc_zoom_level()
                if (spec.min_z is not None and z_now < spec.min_z) or \
                   (spec.max_z is not None and z_now > spec.max_z):
                    self._popup.hide_if_for(vis_for)

    def _apply_visibility_for_current_zoom(self, sensor_id: str):
        tpl = self._items.get(sensor_id)
        if not tpl: return
        dot, label_item, spec = tpl
        z_now = self.viewer._calc_zoom_level()
        visible = True
        if spec.min_z is not None and z_now < spec.min_z: visible = False
        if spec.max_z is not None and z_now > spec.max_z: visible = False
        dot.setVisible(visible)
        if label_item: label_item.setVisible(visible)
        if not visible: self._popup.hide_if_for(sensor_id)

    def _format_popup_html(self, spec: SensorSpec) -> str:
        d = spec.data or {}
        title = str(d.get("name") or spec.label or spec.sensor_id)
        c = spec.color; color_hex = f"#{c.red():02X}{c.green():02X}{c.blue():02X}"
        def row(lbl, key, icon=""):
            val = d.get(key); 
            if not val: return ""
            ic = f"<span style='margin-right:6px'>{icon}</span>" if icon else ""
            return ( "<tr>"
                     f"<td style='padding:6px 12px 6px 0; color:#4B5563; white-space:nowrap;'>{ic}<b>{lbl}:</b></td>"
                     f"<td style='padding:6px 0; color:#111827;'>{val}</td>"
                     "</tr>" )
        rows = [
            row("Moisture","moisture","💧"),
            row("Battery","battery","🔋"),
            row("Last seen","last_seen","⏱"),
            row("Temp","temp","🌡"),
            row("Status","status","•"),
        ]
        preferred = {"name","moisture","battery","last_seen","temp","status"}
        for k,v in d.items():
            if k in preferred or v in (None,""): continue
            rows.append(row(k.replace("_"," ").title(), k))
        status_val = (d.get("status","") or "").strip().lower()
        status_bg = "#10B981" if status_val in ("ok","online","running","good","active") else \
                    "#F59E0B" if status_val in ("degraded","warning") else \
                    "#EF4444" if status_val in ("offline","error","fault","down") else color_hex
        html = (
            "<div style='font-family:Segoe UI,Arial,sans-serif; line-height:1.45; color:#111827; max-width:380px;'>"
            f"<div style='display:flex; align-items:center; gap:10px; background:linear-gradient(135deg, {color_hex}22, #ffffff00); "
            "padding:10px 12px; margin:-2px -2px 10px -2px; border-radius:8px;'>"
            f"<span style='width:12px; height:12px; border-radius:50%; background:{color_hex}; display:inline-block;'></span>"
            f"<span style='font-weight:700; font-size:15px;'>{title}</span>"
            f"<span style='margin-left:auto; font-size:12px; color:#6B7280;'>#{spec.sensor_id}</span>"
            "</div>"
            "<table cellspacing='0' cellpadding='0' style='border-collapse:collapse; font-size:13px; width:auto;'>"
            + "".join(r for r in rows if r) +
            "</table>" +
            (f"<div style='margin-top:10px'><span style='display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; color:#fff; background:{status_bg};'>{status_val.capitalize() or 'Sensor'}</span></div>"
             if status_val else "") +
            "</div>"
        )
        return html

# =========================
# Helpers for GPS/bulk
# =========================

def _split_known_from_data(kwargs: dict):
    known = {k: v for k, v in kwargs.items() if k in KNOWN_SPEC_KEYS}
    data  = {k: v for k, v in kwargs.items() if k not in KNOWN_SPEC_KEYS}
    return known, data

def _first_key(d: dict, keys):
    for k in keys:
        if k in d: return d[k]
    return None

def _y_xyz_to_disk(viewer, z: int, y_xyz: float) -> float:
    return ((1 << z) - 1 - y_xyz) if getattr(viewer, "is_tms", False) else y_xyz

def _y_disk_bounds_to_xyz_bounds(viewer, z: int, y_min_disk: int, y_max_disk: int) -> Tuple[int, int]:
    if getattr(viewer, "is_tms", False):
        n = 1 << z
        y1 = n - 1 - y_max_disk
        y2 = n - 1 - y_min_disk
        return (min(y1, y2), max(y1, y2))
    return (y_min_disk, y_max_disk)

def _color_for_status(status: str) -> QColor:
    s = (status or "").strip().lower()
    if s in ("ok","online","running","good","active"):   return QColor(16,185,129)
    if s in ("warning","degraded"):                      return QColor(245,158,11)
    if s in ("error","offline","fault","down"):          return QColor(239,68,68)
    return QColor(0,120,255)

def _latlon_to_base_xy_if_inside(viewer, lat: float, lon: float, z: int = None) -> Optional[Tuple[float, float]]:
    if z is None:
        z = viewer.max_zoom_fs
    if z not in viewer.z_ranges:
        return None
    try:
        lat = float(lat); lon = float(lon)
    except Exception:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    
    lat = max(min(lat, MERCATOR_MAX_LAT), -MERCATOR_MAX_LAT)
    n = 1 << z
    # Web mercator math
    lat_rad = math.radians(lat)
    xtile_f = (lon + 180.0) / 360.0 * n
    ytile_f_xyz = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    ytile_f_disk = _y_xyz_to_disk(viewer, z, ytile_f_xyz)

    scale = 1 << (z - viewer.min_zoom_fs)
    xb = xtile_f      / float(scale)
    yb = ytile_f_disk / float(scale)

    x_min_base = viewer.ts.z_ranges[viewer.min_zoom_fs][0]
    x_max_base = viewer.ts.z_ranges[viewer.min_zoom_fs][1]
    y_min_base = viewer.ts.z_ranges[viewer.min_zoom_fs][2]
    y_max_base = viewer.ts.z_ranges[viewer.min_zoom_fs][3]

    if x_min_base <= xb < x_min_base + x_max_base + 1 and \
       y_min_base <= yb < y_min_base + y_max_base + 1:
        return xb, yb
    return None

def add_sensor_by_gps_strict(layer: SensorLayer, sensor_id: str, lat: float, lon: float,
                             z: int = None, center: bool = False, **kwargs) -> Optional[SensorSpec]:
    v = layer.viewer
    pos = _latlon_to_base_xy_if_inside(v, lat, lon, z=z)
    if pos is None:
        return None
    xb, yb = pos
    known, data = _split_known_from_data(kwargs)
    if "color" not in known and "status" in data:
        known["color"] = _color_for_status(data.get("status"))
    spec = SensorSpec(sensor_id=sensor_id, xb=xb, yb=yb, **known, data=data)
    layer.add_sensor(spec)
    if center:
        v.centerOn((xb - v._x_min_base) * TILE_SIZE, (yb - v._y_min_base) * TILE_SIZE)
    return spec

def add_sensors_by_gps_bulk(layer: SensorLayer, sensors: list, z: int = None,
                            center_on_first: bool = False, default_radius_px: float = 0.1) -> Dict[str, list]:
    placed, skipped = [], []
    first_spec: Optional[SensorSpec] = None
    for s in sensors:
        sid = _first_key(s, ID_KEYS)
        lat = _first_key(s, LAT_KEYS)
        lon = _first_key(s, LON_KEYS)
        if sid is None or lat is None or lon is None:
            skipped.append(sid or "<missing-id/coords>")
            continue
        known = {k: s[k] for k in KNOWN_SPEC_KEYS if k in s}
        known.setdefault("radius_px", default_radius_px)
        data  = {k: v for k, v in s.items() if k not in KNOWN_SPEC_KEYS and k not in ID_KEYS + LAT_KEYS + LON_KEYS}
        spec = add_sensor_by_gps_strict(layer, sid, lat, lon, z=z, center=False, **known, **data)
        if spec:
            placed.append(sid)
            if first_spec is None: first_spec = spec
        else:
            skipped.append(sid)
    if center_on_first and first_spec:
        v = layer.viewer
        layer.viewer.centerOn((first_spec.xb - v.ts.z_ranges[v.min_zoom_fs][0]) * TILE_SIZE, (first_spec.yb - v.ts.z_ranges[v.min_zoom_fs][2]) * TILE_SIZE)
    print(f"[BULK] placed={len(placed)} skipped={len(skipped)}")
    return {"placed": placed, "skipped": skipped}

def dataset_bbox_latlon(viewer, z: int = None) -> Tuple[float, float, float, float]:
    if z is None:
        z = viewer.max_zoom_fs
    if z not in viewer.z_ranges:
        raise ValueError(f"Zoom z={z} not available.")
    x_min, x_max, y_min_disk, y_max_disk = viewer.z_ranges[z]
    n = 1 << z
    y_xyz_min, y_xyz_max = _y_disk_bounds_to_xyz_bounds(viewer, z, y_min_disk, y_max_disk)
    def tile2lon(x): return x / n * 360.0 - 180.0
    def tile2lat(y):
        t = math.pi * (1.0 - 2.0 * (y / n)); return math.degrees(math.atan(math.sinh(t)))
    lon_min = tile2lon(x_min); lon_max = tile2lon(x_max + 1)
    lat_max = tile2lat(y_xyz_min); lat_min = tile2lat(y_xyz_max + 1)
    print(f"[COVERAGE z={z}] lon:[{lon_min:.6f}..{lon_max:.6f}]  lat:[{lat_min:.6f}..{lat_max:.6f}]")
    return (lat_min, lat_max, lon_min, lon_max)