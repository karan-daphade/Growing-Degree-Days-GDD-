#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate KML files (all-in-one + grid-wise) from 'farmer_grid_mapping' table.

Requirements:
  pip install python-dotenv psycopg2-binary simplekml shapely

Environment (.env):
  DATABASE_URL=postgresql://user:pass@host:port/dbname
  # (or POSTGRES_URL=...)

Outputs:
  - ./kml_files/all_farms_and_grids.kml
  - ./kml_files/grid_<Grid_ID or lat_lon>.kml
"""

import os
import sys
import logging
from datetime import date
from collections import defaultdict

from dotenv import load_dotenv

import psycopg2
import psycopg2.extras

from shapely import wkb
from shapely.geometry import Polygon, MultiPolygon

import simplekml

# ----------------------------- Logging ---------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ----------------------------- Helpers ---------------------------------------
# Column names with spaces/Marathi labels from the schema:
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

def get_env_db_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("DB_URL")
    if not url:
        raise RuntimeError("Database URL not found. Please set DB_URL (or DATABASE_URL/POSTGRES_URL) in your .env")

    # Fix for SQLAlchemy-style URLs
    if url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return url


def safe_date_str(d):
    """Return YYYY-MM-DD for date/datetime, else '-' for None/empty."""
    if d is None:
        return "-"
    if isinstance(d, (date,)):
        return d.isoformat()
    # psycopg2 may already parse to date; if string, return as-is
    try:
        return str(d)
    except Exception:
        return "-"

def safe_str(v):
    return "-" if v in (None, "") else str(v)

def ewkb_hex_to_geom(hex_text):
    """Parse EWKB hex (SRID 4326) to a Shapely geometry. Returns None on failure."""
    if not hex_text:
        return None
    try:
        # Shapely can load hex directly. EWKB with SRID is acceptable.
        geom = wkb.loads(hex_text, hex=True)
        return geom
    except Exception as e:
        logging.warning("Failed to parse EWKB hex geometry: %s", e)
        try:
            # Fallback: interpret as bytes explicitly
            geom = wkb.loads(bytes.fromhex(hex_text))
            return geom
        except Exception as e2:
            logging.error("Fallback EWKB parse also failed: %s", e2)
            return None

def polygon_coords_for_kml(shapely_polygon: Polygon):
    """
    Convert a Shapely Polygon into a KML-compliant coordinate ring list:
    List[(lon, lat, alt=0)] for the outer boundary.
    Note: KML expects lon,lat[,alt]; altitude 0 here.
    """
    # Exterior ring only; if holes needed in the future, add inner boundaries.
    if shapely_polygon.is_empty:
        return []
    # Ensure closed ring for KML (first=last); simplekml will handle it, but we make it explicit.
    coords = [(x, y, 0) for x, y in shapely_polygon.exterior.coords]
    # Just in case, enforce closure
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords

def grid_rectangle_polygon(grid_lat: float, grid_lon: float):
    """
    Build a 0.1° x 0.1° rectangle polygon for the grid (lon,lat).
    Coordinates are in lon,lat order (SRID 4326).
    """
    if grid_lat is None or grid_lon is None:
        return None
    try:
        lat0 = float(grid_lat)
        lon0 = float(grid_lon)
    except (TypeError, ValueError):
        return None

    lat1 = lat0 + 0.1
    lon1 = lon0 + 0.1

    # Shapely Polygon expects (x=lon, y=lat)
    ring = [
        (lon0, lat0),
        (lon1, lat0),
        (lon1, lat1),
        (lon0, lat1),
        (lon0, lat0),
    ]
    return Polygon(ring)

def kml_color(a, r, g, b):
    """
    Return KML color string in aabbggrr order (alpha, blue, green, red) as hex.
    Inputs are 0-255 ints.
    """
    return f"{a:02x}{b:02x}{g:02x}{r:02x}"

# Styles (KML uses aabbggrr)
ALPHA_SEMI = 0x7F  # ~50% transparent
ALPHA_LIGHT = 0x33 # lighter fill
ALPHA_SOLID = 0xFF

# Yellow fill (r=255,g=255,b=0), blue outline (r=0,g=0,b=255)
FARM_FILL_COLOR = kml_color(ALPHA_SEMI, 255, 255, 0)     # ~50% transparent yellow
FARM_LINE_COLOR = kml_color(ALPHA_SOLID, 255, 247, 143)      # solid blue outline

# Grid: light blue fill & blue outline
GRID_FILL_COLOR = kml_color(ALPHA_LIGHT, 0, 0, 0)    # light transparent sky-blue
GRID_LINE_COLOR = kml_color(ALPHA_SOLID, 249, 247, 241)      # solid blue outline

def build_farm_description(row: dict) -> str:
    """
    Build the KML description HTML for a farm placemark.
    Includes: Farmer ID, Farmer Name, Grid ID, Cluster name, Village,
              Cotton sowing date, Intercrop name.
    """
    farmer_id = safe_str(row.get(COL["farmer_id"]))
    farmer_name = safe_str(row.get(COL["farmer_name"]))
    grid_id = safe_str(row.get(COL["grid_id"]))
    cluster = safe_str(row.get(COL["cluster"]))
    village = safe_str(row.get(COL["village"]))
    cotton_dt = safe_date_str(row.get(COL["cotton_sowing_date"]))
    intercrop = safe_str(row.get(COL["intercrop_name"]))

    html = f"""
    <![CDATA[
      <table border="0" cellpadding="2" cellspacing="0">
        <tr><td><b>Farmer ID</b></td><td>{farmer_id}</td></tr>
        <tr><td><b>Farmer Name</b></td><td>{farmer_name}</td></tr>
        <tr><td><b>Grid ID</b></td><td>{grid_id}</td></tr>
        <tr><td><b>Cluster</b></td><td>{cluster}</td></tr>
        <tr><td><b>Village</b></td><td>{village}</td></tr>
        <tr><td><b>Cotton sowing date</b></td><td>{cotton_dt}</td></tr>
        <tr><td><b>Intercrop</b></td><td>{intercrop}</td></tr>
      </table>
    ]]>
    """
    return html

def build_grid_description(grid_id: str, grid_lat: float, grid_lon: float, farms_count: int) -> str:
    html = f"""
    <![CDATA[
      <b>Grid</b><br/>
      <b>Grid ID:</b> {safe_str(grid_id)}<br/>
      <b>Grid Lat,Lon:</b> {safe_str(grid_lat)}, {safe_str(grid_lon)}<br/>
      <b>Farms in this grid:</b> {farms_count}
    ]]>
    """
    return html

def add_polygon_placemark(folder, name: str, description: str, coords_3d, fill_color, line_color, line_width=2.0):
    """Add a single polygon placemark to a simplekml Folder."""
    pol = folder.newpolygon(name=name)
    pol.outerboundaryis = coords_3d  # list[(lon,lat,alt)]
    pol.description = description
    pol.style.polystyle.color = fill_color
    pol.style.linestyle.color = line_color
    pol.style.linestyle.width = line_width
    pol.style.polystyle.outline = 1
    pol.style.polystyle.fill = 1
    return pol

def add_multipolygon_placemark(folder, name: str, description: str, poly_list_coords3d, fill_color, line_color, line_width=2.0):
    """Add a MultiGeometry placemark with several polygon parts."""
    mg = folder.newmultigeometry(name=name)
    mg.description = description
    for coords_3d in poly_list_coords3d:
        pol = mg.newpolygon()
        pol.outerboundaryis = coords_3d
        pol.style.polystyle.color = fill_color
        pol.style.linestyle.color = line_color
        pol.style.linestyle.width = line_width
        pol.style.polystyle.outline = 1
        pol.style.polystyle.fill = 1
    return mg

# ----------------------------- Core ------------------------------------------
def fetch_rows(conn):
    """Fetch all rows from farmer_grid_mapping as a list of dicts."""
    sql = "SELECT * FROM farmer_grid_mapping;"
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        return [dict(r) for r in rows]

def main():
    # Create output directory
    output_dir = "kml_files"
    os.makedirs(output_dir, exist_ok=True)  # Create folder if it doesn't exist
    logging.info("Output directory set to: %s", os.path.abspath(output_dir))

    try:
        db_url = get_env_db_url()
    except Exception as e:
        logging.error("Could not load DB URL from .env: %s", e)
        sys.exit(1)

    try:
        conn = psycopg2.connect(dsn=db_url)
    except Exception as e:
        logging.error("Database connection failed: %s", e)
        sys.exit(2)

    try:
        rows = fetch_rows(conn)
        if not rows:
            logging.warning("No rows found in farmer_grid_mapping.")
    except Exception as e:
        logging.error("Query failed: %s", e)
        conn.close()
        sys.exit(3)
    finally:
        conn.close()

    logging.info("Fetched %d row(s).", len(rows))

    # Map: grid_key -> {"grid_id": str, "grid_lat": float, "grid_lon": float, "polygon": shapely Polygon}
    grids = {}
    # Map: grid_key -> list of row dicts
    grid_to_farms = defaultdict(list)

    # Pre-parse geometries and assign rows to grids
    parsed = []
    for r in rows:
        geom_hex = r.get(COL["geom"])
        geom = ewkb_hex_to_geom(geom_hex)
        if geom is None or geom.is_empty:
            logging.warning("Skipping row with invalid/empty geometry (fid=%s).", r.get(COL["fid"]))
            continue

        # Accept only Polygon / MultiPolygon
        if not isinstance(geom, (Polygon, MultiPolygon)):
            logging.warning("Skipping non-polygon geometry type '%s' (fid=%s).", geom.geom_type, r.get(COL["fid"]))
            continue

        # Grid info
        grid_lat = r.get(COL["grid_lat"])
        grid_lon = r.get(COL["grid_lon"])
        grid_id = r.get(COL["grid_id"]) or ""

        grid_poly = grid_rectangle_polygon(grid_lat, grid_lon)
        if grid_poly is None:
            logging.warning("Row missing/invalid grid_lat/grid_lon (fid=%s).", r.get(COL["fid"]))

        # Define grid key: prefer Grid_ID if present, else lat_lon
        if grid_id and str(grid_id).strip():
            grid_key = f"GRIDID::{grid_id}"
            disp_grid_id = grid_id
        else:
            # fallback key
            disp_grid_id = f"{grid_lat}_{grid_lon}"
            grid_key = f"LATLON::{disp_grid_id}"

        # Keep unique grid polygon (first occurrence wins, unless missing)
        if grid_key not in grids and grid_poly is not None:
            grids[grid_key] = {
                "grid_id": grid_id or disp_grid_id,
                "grid_lat": grid_lat,
                "grid_lon": grid_lon,
                "polygon": grid_poly,
            }

        # Assign farm to grid bucket
        grid_to_farms[grid_key].append({**r, "_geom": geom, "_grid_id_display": disp_grid_id})

        parsed.append(r)

    # ---------------- All-in-one KML ----------------
    kml = simplekml.Kml()
    folder_farms = kml.newfolder(name="Farm Polygons")
    folder_grids = kml.newfolder(name="Grids")

    # Add all unique grid rectangles
    for grid_key, g in grids.items():
        grid_coords3d = polygon_coords_for_kml(g["polygon"])
        farms_count = len(grid_to_farms.get(grid_key, []))
        desc = build_grid_description(g["grid_id"], g["grid_lat"], g["grid_lon"], farms_count)
        add_polygon_placemark(
            folder=folder_grids,
            name=f"Grid {g['grid_id']}",
            description=desc,
            coords_3d=grid_coords3d,
            fill_color=GRID_FILL_COLOR,
            line_color=GRID_LINE_COLOR,
            line_width=2.0
        )

    # Add all farm polygons
    for grid_key, farm_rows in grid_to_farms.items():
        for r in farm_rows:
            geom = r["_geom"]
            name = safe_str(r.get(COL["farmer_name"]))
            desc = build_farm_description(r)

            if isinstance(geom, Polygon):
                coords3d = polygon_coords_for_kml(geom)
                if not coords3d:
                    continue
                add_polygon_placemark(
                    folder=folder_farms,
                    name=name,
                    description=desc,
                    coords_3d=coords3d,
                    fill_color=FARM_FILL_COLOR,
                    line_color=FARM_LINE_COLOR,
                    line_width=2.0
                )
            elif isinstance(geom, MultiPolygon):
                polys_coords = []
                for part in geom.geoms:
                    part_coords3d = polygon_coords_for_kml(part)
                    if part_coords3d:
                        polys_coords.append(part_coords3d)
                if not polys_coords:
                    continue
                add_multipolygon_placemark(
                    folder=folder_farms,
                    name=name,
                    description=desc,
                    poly_list_coords3d=polys_coords,
                    fill_color=FARM_FILL_COLOR,
                    line_color=FARM_LINE_COLOR,
                    line_width=2.0
                )

    # Save all-in-one KML in kml_files folder
    all_kml_path = os.path.join(output_dir, "all_farms_and_grids.kml")
    all_kml_path = os.path.abspath(all_kml_path)
    kml.save(all_kml_path)
    logging.info("Wrote %s", all_kml_path)

    # ---------------- Grid-wise KMLs ----------------
    for grid_key, farm_rows in grid_to_farms.items():
        g = grids.get(grid_key)
        # Create per-grid KML regardless of whether we had a valid grid rectangle.
        kml_grid = simplekml.Kml()
        folder_grid = kml_grid.newfolder(name="Grid")
        folder_farms_grid = kml_grid.newfolder(name="Farm Polygons")

        # Name for output file
        grid_id_disp = (g["grid_id"] if g and g.get("grid_id") else farm_rows[0].get("_grid_id_display") or "unknown").replace(" ", "_")
        # Save grid-wise KML in kml_files folder
        out_path = os.path.join(output_dir, f"{grid_id_disp}.kml")
        out_path = os.path.abspath(out_path)

        # Add grid rectangle if available
        if g and g.get("polygon") is not None:
            grid_coords3d = polygon_coords_for_kml(g["polygon"])
            desc = build_grid_description(g["grid_id"], g["grid_lat"], g["grid_lon"], len(farm_rows))
            add_polygon_placemark(
                folder=folder_grid,
                name=f"Grid {g['grid_id']}",
                description=desc,
                coords_3d=grid_coords3d,
                fill_color=GRID_FILL_COLOR,
                line_color=GRID_LINE_COLOR,
                line_width=0.5
            )

        # Add farm polygons within this grid
        for r in farm_rows:
            geom = r["_geom"]
            name = safe_str(r.get(COL["farmer_name"]))
            desc = build_farm_description(r)

            if isinstance(geom, Polygon):
                coords3d = polygon_coords_for_kml(geom)
                if not coords3d:
                    continue
                add_polygon_placemark(
                    folder=folder_farms_grid,
                    name=name,
                    description=desc,
                    coords_3d=coords3d,
                    fill_color=FARM_FILL_COLOR,
                    line_color=FARM_LINE_COLOR,
                    line_width=1.0
                )
            elif isinstance(geom, MultiPolygon):
                polys_coords = []
                for part in geom.geoms:
                    part_coords3d = polygon_coords_for_kml(part)
                    if part_coords3d:
                        polys_coords.append(part_coords3d)
                if not polys_coords:
                    continue
                add_multipolygon_placemark(
                    folder=folder_farms_grid,
                    name=name,
                    description=desc,
                    poly_list_coords3d=polys_coords,
                    fill_color=FARM_FILL_COLOR,
                    line_color=FARM_LINE_COLOR,
                    line_width=2.0
                )

        kml_grid.save(out_path)
        logging.info("Wrote %s", out_path)

    logging.info("Done.")

if __name__ == "__main__":
    main()