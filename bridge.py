from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import requests
import xmltodict

try:
    import config
    CBP_URL = getattr(config, "CBP_URL", "https://bwt.cbp.gov/xml/bwt.xml")
except ImportError:
    CBP_URL = os.getenv("CBP_URL", "https://bwt.cbp.gov/xml/bwt.xml")

LANE_KEYS = {
    "standard":   ["passenger_vehicle_lanes", "standard_lanes", "delay_minutes"],
    "ready":      ["passenger_vehicle_lanes", "ready_lanes",    "delay_minutes"],
    "sentri":     ["passenger_vehicle_lanes", "NEXUS_SENTRI_lanes", "delay_minutes"],
    "pedestrian": ["pedestrian_lanes",        "standard_lanes", "delay_minutes"],
}

NAME_MAP = [
    ("paso del norte", "Paso Del Norte (PDN)"),
    ("pdn",            "Paso Del Norte (PDN)"),
    ("bridge of the amer", "Bridge of the Americas (BOTA)"),
    ("bota",           "Bridge of the Americas (BOTA)"),
    ("ysleta",         "Ysleta-Zaragoza"),
    ("zaragoza",       "Ysleta-Zaragoza"),
    ("stanton",        "Stanton DCL (SENTRI)"),
    ("dcl",            "Stanton DCL (SENTRI)"),
]

def _leaf(d: dict, path: list) -> Optional[str]:
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    if isinstance(cur, dict):
        cur = cur.get("#text") or cur.get("value")
    s = (cur or "").strip()
    return s or None

def _as_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(s)
    except (TypeError, ValueError):
        return None

def _normalize(label: str) -> Optional[str]:
    low = (label or "").lower()
    for needle, mapped in NAME_MAP:
        if needle in low:
            return mapped
    return None

def fetch_waits(mode: str, city: str = "El Paso", border: str = "Mexican Border") -> Dict[str, int]:
    if mode not in LANE_KEYS:
        raise ValueError(f"mode must be one of {list(LANE_KEYS)}")

    r = requests.get(CBP_URL, timeout=15)
    r.raise_for_status()
    data = xmltodict.parse(r.content)

    ports = (data.get("border_wait_time") or data).get("port")
    if not ports:
        return {}
    if isinstance(ports, dict):
        ports = [ports]

    waits: Dict[str, int] = {}
    for p in ports:
        port_name = (p.get("port_name") or "").strip()
        crossing  = (p.get("crossing_name") or "").strip()
        label_raw = crossing or port_name

        if city.lower() not in (port_name + " " + crossing).lower():
            continue
        if border.lower() not in (p.get("border") or "").lower():
            continue

        minutes = _as_int(_leaf(p, LANE_KEYS[mode]))
        if minutes is None:
            continue

        key = _normalize(label_raw)
        if key:
            waits[key] = minutes

    return waits


@dataclass(frozen=True)
class Bridge:
    name: str
    lat: float
    lng: float

BRIDGES: Dict[str, Bridge] = {
    "Paso Del Norte (PDN)":          Bridge("Paso Del Norte (PDN)", 31.7586, -106.4869),
    "Bridge of the Americas (BOTA)": Bridge("Bridge of the Americas (BOTA)", 31.7673, -106.4678),
    "Ysleta-Zaragoza":               Bridge("Ysleta-Zaragoza", 31.7772, -106.4487),
    "Stanton DCL (SENTRI)":          Bridge("Stanton DCL (SENTRI)", 31.7584, -106.4861),
}

def _dm_seconds(origin: Tuple[float, float], dest: Tuple[float, float], key: str) -> Optional[int]:
    """Distance Matrix time (seconds) with traffic; None on API issues."""
    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params={
                "origins": f"{origin[0]},{origin[1]}",
                "destinations": f"{dest[0]},{dest[1]}",
                "mode": "driving",
                "departure_time": "now",
                "traffic_model": "best_guess",
                "key": key,
            },
            timeout=15,
        ).json()
    except requests.RequestException:
        return None

    if r.get("status") not in (None, "OK"):
        return None
    try:
        elem = r["rows"][0]["elements"][0]
        if elem.get("status") != "OK":
            return None
        dur = elem.get("duration_in_traffic") or elem.get("duration")
        return int(dur["value"]) if dur else None
    except (IndexError, KeyError, TypeError, ValueError):
        return None

def fastest_crossing(origin: Tuple[float, float], dest: Tuple[float, float], mode: str, server_key: str) -> dict:
    """Compute winner and per-bridge breakdown."""
    waits = fetch_waits(mode)
    if not waits:
        raise RuntimeError("No wait times available for the selected lane.")

    best = {"bridge": None, "total_s": float("inf")}
    breakdown: Dict[str, dict] = {}

    for name, b in BRIDGES.items():
        wait_min = waits.get(name)
        if wait_min is None:
            continue

        to_s   = _dm_seconds(origin, (b.lat, b.lng), server_key)
        from_s = _dm_seconds((b.lat, b.lng), dest, server_key)
        if to_s is None or from_s is None:
            continue

        total = wait_min * 60 + to_s + from_s
        breakdown[name] = {
            "wait_min": wait_min,
            "to_bridge_s": to_s,
            "from_bridge_s": from_s,
            "total_s": total,
        }
        if total < best["total_s"]:
            best = {"bridge": name, "total_s": total}

    if not breakdown:
        raise RuntimeError("No viable routes (routing failed or lanes closed).")

    best["breakdown"] = breakdown
    return best
