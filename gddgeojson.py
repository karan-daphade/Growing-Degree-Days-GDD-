#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate GeoJSON files (all-in-one + grid-wise) from 'farmer_grid_mapping' table.

Requirements:
  pip install python-dotenv psycopg2-binary shapely

Environment (.env):
  DATABASE_URL=postgresql://user:pass@host:port/dbname
  # (or POSTGRES_URL=...)

Outputs:
  - ./geojson_files/all_farms_and_grids.geojson
  - ./geojson_files/<grid_id_or_lat_lon>.geojson
"""

import os
import sys
import json
import logging
from datetime import date
from collections import defaultdict

from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

from shapely import wkb
from shapely.geometry import Polygon, MultiPolygon, mapping

# ----------------------------- Logging ---------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ----------------------------- Column map (DB -> logical) --------------------
COL = {
    "fid": "fid",
    "farmer_id": "Farmer ID",
    "farmer_name": "Farmer Name",
    "village": "Village",
    "cluster": "Cluster name",
    "cotton_sowing_date": "Cotton sowing date ( कापसाची पेरणी त)",
    "intercrop_name": "Intercrop name (आंतरपिकाचे नाव)",
    "geom": "geom",
    "grid_lat": "grid_lat",
    "grid_lon": "grid_lon",
    "grid_id": "Grid_ID",
}

# ----------------------------- Helpers ---------------------------------------
def get_env_db_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("DB_URL")
    if not url:
        raise RuntimeError("Database URL not found. Please set DB_URL (or DATABASE_URL/POSTGRES_URL) in your .env")
    if url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return url

def safe_date_str(d):
    if d is None:
        return "-"
    if isinstance(d, (date,)):
        return d.isoformat()
    try:
        return str(d)
    except Exception:
        return "-"

def safe_str(v):
    return "-" if v in (None, "") else str(v)

def to_float_or_none(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None

def ewkb_hex_to_geom(hex_text):
    if not hex_text:
        return None
    try:
        return wkb.loads(hex_text, hex=True)
    except Exception:
        try:
            return wkb.loads(bytes.fromhex(hex_text))
        except Exception:
            return None

def grid_rectangle_polygon(grid_lat: float, grid_lon: float):
    if grid_lat is None or grid_lon is None:
        return None
    try:
        lat0 = float(grid_lat)
        lon0 = float(grid_lon)
    except (TypeError, ValueError):
        return None
    lat1 = lat0 + 0.1
    lon1 = lon0 + 0.1
    ring = [
        (lon0, lat0),
        (lon1, lat0),
        (lon1, lat1),
        (lon0, lat1),
        (lon0, lat0),
    ]
    return Polygon(ring)

def fetch_rows(conn):
    sql = "SELECT * FROM farmer_grid_mapping;"
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        return [dict(r) for r in rows]

# ----------------------------- Properties (legacy keys for Grid_Map.py) ------
def farm_properties(row: dict, farms_count=None, grid_lat=None, grid_lon=None) -> dict:
    """
    Emit properties using the legacy keys expected by Grid_Map.py:
      - "Farmer Name", "Farmer ID", "Village", "Cluster",
        "Cotton sowing date", "Intercrop", "Grid ID", "name"
    PLUS (to avoid tooltip errors in the Grids layer):
      - "Farms in this grid", "Grid Lat,Lon"
    Also include style keys and machine-readable duplicates.
    """
    farmer_id = safe_str(row.get(COL["farmer_id"]))
    farmer_name = safe_str(row.get(COL["farmer_name"]))
    grid_id = safe_str(row.get(COL["grid_id"]))
    village = safe_str(row.get(COL["village"]))
    cluster = safe_str(row.get(COL["cluster"]))
    intercrop = safe_str(row.get(COL["intercrop_name"]))
    sow_date = safe_date_str(row.get(COL["cotton_sowing_date"]))

    props = {
        # legacy / UI-expected keys
        "Farmer ID": farmer_id,
        "Farmer Name": farmer_name,
        "Village": village,
        "Cluster": cluster,
        "Cotton sowing date": sow_date,  # NOTE: exactly as Grid_Map.py expects
        "Intercrop": intercrop,
        "Grid ID": grid_id,
        "name": farmer_name,

        # styles used by Grid_Map.py style functions
        "stroke": "#fff78f",
        "stroke-width": 2.0,
        "fill": "#ffff007f",

        # machine-readable duplicates (optional)
        "feature_type": "farm",
        "farmer_id": farmer_id,
        "farmer_name": farmer_name,
        "village": village,
        "cluster": cluster,
        "intercrop_name": intercrop,
        "grid_id": grid_id,
    }

    # Extra fields so farms won't break the Grids layer tooltip/popups
    if farms_count is not None:
        props["Farms in this grid"] = int(farms_count)
    if grid_lat is not None and grid_lon is not None:
        props["Grid Lat,Lon"] = f"{grid_lat},{grid_lon}"

    return props

def grid_properties(grid_id, grid_lat, grid_lon, farms_count) -> dict:
    """
    Emit properties using the legacy keys expected by Grid_Map.py:
      - "Grid ID", "Farms in this grid", "Grid Lat,Lon", "name"
    Also include style keys and machine-readable duplicates.
    """
    grid_id_s = safe_str(grid_id)
    latlon_s = "-" if (grid_lat is None or grid_lon is None) else f"{grid_lat},{grid_lon}"
    return {
        # legacy / UI-expected keys
        "Grid ID": grid_id_s,
        "Farms in this grid": int(farms_count or 0),
        "Grid Lat,Lon": latlon_s,
        "name": grid_id_s,

        # styles used by Grid_Map.py style functions
        "stroke": "#f9f7f1",
        "stroke-width": 1.5,
        "fill": "#00000033",

        # machine-readable duplicates (optional)
        "feature_type": "grid",
        "grid_id": grid_id_s,
        "grid_lat": to_float_or_none(grid_lat),
        "grid_lon": to_float_or_none(grid_lon),
        "farms_count": int(farms_count or 0),
    }

# ----------------------------- GeoJSON helpers -------------------------------
def feature(geom, properties):
    """Create a GeoJSON Feature (no CRS per RFC 7946; WGS84 assumed)."""
    return {
        "type": "Feature",
        "geometry": mapping(geom),  # handles Polygon/MultiPolygon
        "properties": properties,
    }

def feature_collection(features):
    return {
        "type": "FeatureCollection",
        "features": features,
    }

# ----------------------------- Core ------------------------------------------
def main():
    # Output directory
    output_dir = "geojson_files"
    os.makedirs(output_dir, exist_ok=True)
    logging.info("Output directory: %s", os.path.abspath(output_dir))

    # DB connect
    try:
        db_url = get_env_db_url()
    except Exception as e:
        logging.error("Could not load DB URL: %s", e)
        sys.exit(1)

    try:
        conn = psycopg2.connect(dsn=db_url)
    except Exception as e:
        logging.error("Database connection failed: %s", e)
        sys.exit(2)

    # Fetch
    try:
        rows = fetch_rows(conn)
    except Exception as e:
        logging.error("Query failed: %s", e)
        conn.close()
        sys.exit(3)
    finally:
        conn.close()

    logging.info("Fetched %d row(s).", len(rows) if rows else 0)

    grids = {}  # grid_key -> {grid_id, grid_lat, grid_lon, polygon}
    grid_to_farms = defaultdict(list)

    for r in rows or []:
        geom_hex = r.get(COL["geom"])
        geom = ewkb_hex_to_geom(geom_hex)
        if geom is None or geom.is_empty:
            logging.warning("Skipping row with invalid/empty geometry (fid=%s).", r.get(COL["fid"]))
            continue
        if not isinstance(geom, (Polygon, MultiPolygon)):
            logging.warning("Skipping non-polygon geometry type '%s' (fid=%s).", geom.geom_type, r.get(COL["fid"]))
            continue

        grid_lat = r.get(COL["grid_lat"])
        grid_lon = r.get(COL["grid_lon"])
        grid_id = r.get(COL["grid_id"]) or ""

        grid_poly = grid_rectangle_polygon(grid_lat, grid_lon)
        if grid_id and str(grid_id).strip():
            grid_key = f"GRIDID::{grid_id}"
            disp_grid_id = grid_id
        else:
            disp_grid_id = f"{grid_lat}_{grid_lon}"
            grid_key = f"LATLON::{disp_grid_id}"

        if grid_key not in grids and grid_poly is not None:
            grids[grid_key] = {
                "grid_id": grid_id or disp_grid_id,
                "grid_lat": grid_lat,
                "grid_lon": grid_lon,
                "polygon": grid_poly,
            }

        grid_to_farms[grid_key].append({**r, "_geom": geom, "_grid_id_display": disp_grid_id})

    # ---------------- Combined GeoJSON ----------------
    combined_features = []

    # Grids first
    for grid_key, g in grids.items():
        farms_count = len(grid_to_farms.get(grid_key, []))
        props = grid_properties(g["grid_id"], g["grid_lat"], g["grid_lon"], farms_count)
        combined_features.append(feature(g["polygon"], props))

    # Farms (add grid context to every farm so grids tooltip never breaks)
    for grid_key, farm_rows in grid_to_farms.items():
        g = grids.get(grid_key)
        farms_count = len(farm_rows)
        glat = g["grid_lat"] if g else None
        glon = g["grid_lon"] if g else None
        for r in farm_rows:
            geom = r["_geom"]
            props = farm_properties(r, farms_count=farms_count, grid_lat=glat, grid_lon=glon)
            combined_features.append(feature(geom, props))

    all_path = os.path.abspath(os.path.join(output_dir, "all_farms_and_grids.geojson"))
    with open(all_path, "w", encoding="utf-8") as f:
        json.dump(feature_collection(combined_features), f, ensure_ascii=False)
    logging.info("Wrote %s", all_path)

    # ---------------- Grid-wise GeoJSONs ----------------
    for grid_key, farm_rows in grid_to_farms.items():
        g = grids.get(grid_key)
        features = []

        # Grid rectangle if available
        grid_id_disp = (g["grid_id"] if g and g.get("grid_id") else farm_rows[0].get("_grid_id_display") or "unknown")
        if g and g.get("polygon") is not None:
            props = grid_properties(g["grid_id"], g["grid_lat"], g["grid_lon"], len(farm_rows))
            features.append(feature(g["polygon"], props))

        # Farm features with grid context
        farms_count = len(farm_rows)
        glat = g["grid_lat"] if g else None
        glon = g["grid_lon"] if g else None
        for r in farm_rows:
            geom = r["_geom"]
            props = farm_properties(r, farms_count=farms_count, grid_lat=glat, grid_lon=glon)
            features.append(feature(geom, props))

        out_path = os.path.abspath(os.path.join(output_dir, f"{str(grid_id_disp).replace(' ', '_')}.geojson"))
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(feature_collection(features), f, ensure_ascii=False)
        logging.info("Wrote %s", out_path)

    logging.info("Done.")

if __name__ == "__main__":
    main()