# pages/Grid_Map.py
# -------------------------------------------------
import os
import json
import math
from typing import Dict, Any, List, Tuple, Optional

import streamlit as st
import folium
from folium.plugins import MousePosition, Fullscreen, MiniMap, MeasureControl
from streamlit_folium import st_folium

st.set_page_config(page_title="Cluster Grid Map", layout="wide")

DATA_DIR = "geojson_files"
ALL_FILE = "all_farms_and_grids.geojson"

# ----------------------------- HELPERS ---------------------------------------
def list_geojson_files(dirpath: str) -> List[str]:
    if not os.path.isdir(dirpath):
        return []
    files = sorted([f for f in os.listdir(dirpath) if f.lower().endswith(".geojson")])
    if ALL_FILE in files:
        files.remove(ALL_FILE)
        files.insert(0, ALL_FILE)
    return files

def load_geojson(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ---- NEW: robust, exclusive classification (prefer explicit feature_type) ---
def is_grid_feature(props: Dict[str, Any]) -> bool:
    # Prefer explicit marker from generator
    if props.get("feature_type") == "grid":
        return True
    # Fallback for older files that lack feature_type:
    # require BOTH grid-only keys so farms don't get misclassified
    return ("Farms in this grid" in props) and ("Grid Lat,Lon" in props)

def is_farm_feature(props: Dict[str, Any]) -> bool:
    # Prefer explicit marker
    if props.get("feature_type") == "farm":
        return True
    # Fallback for older files
    return ("Farmer ID" in props) or ("Farmer Name" in props)

def split_feature_collections(fc: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    grids, farms = [], []
    for feat in fc.get("features", []):
        props = feat.get("properties", {}) or {}
        if is_grid_feature(props):
            grids.append(feat)
        elif is_farm_feature(props):  # <-- exclusive split: no double-classify
            farms.append(feat)
    return (
        {"type": "FeatureCollection", "features": grids},
        {"type": "FeatureCollection", "features": farms},
    )

def features_bounds(features: List[Dict[str, Any]]) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    min_lon = min_lat = math.inf
    max_lon = max_lat = -math.inf

    def consume_coords(coords):
        nonlocal min_lon, min_lat, max_lon, max_lat
        for ring in coords:
            for lon, lat in ring:
                min_lon = min(min_lon, lon)
                min_lat = min(min_lat, lat)
                max_lon = max(max_lon, lon)
                max_lat = max(max_lat, lat)

    for f in features:
        geom = f.get("geometry", {})
        gtype = geom.get("type")
        if gtype == "Polygon":
            consume_coords(geom.get("coordinates", []))
        elif gtype == "MultiPolygon":
            for poly in geom.get("coordinates", []):
                consume_coords(poly)

    if not math.isfinite(min_lon) or not math.isfinite(min_lat):
        return None
    return ((min_lat, min_lon), (max_lat, max_lon))

def center_from_bounds(bounds) -> List[float]:
    (min_lat, min_lon), (max_lat, max_lon) = bounds
    return [(min_lat + max_lat) / 2.0, (min_lon + max_lon) / 2.0]

def grid_style(feature):
    props = feature.get("properties", {}) or {}
    return {
        "fillOpacity": 0.25,
        "weight": float(props.get("stroke-width", 1.5)),
        "color": props.get("stroke", "#f9f7f1"),
        "fillColor": props.get("fill", "#00000033"),
    }

def farm_style(feature):
    props = feature.get("properties", {}) or {}
    return {
        "fillOpacity": 0.35,
        "weight": float(props.get("stroke-width", 2.0)),
        "color": props.get("stroke", "#fff78f"),
        "fillColor": props.get("fill", "#ffff007f"),
    }

# ----------------------------- UI: SIDEBAR -----------------------------------
st.sidebar.title("Grid Map - Controls")

files = list_geojson_files(DATA_DIR)
if not files:
    st.sidebar.warning(f"No GeoJSON files found in `{DATA_DIR}`")
    st.stop()

selected_file = st.sidebar.selectbox("Select GeoJSON", files, index=0)
path = os.path.join(DATA_DIR, selected_file)
fc_all = load_geojson(path)
if not fc_all:
    st.error("Failed to load GeoJSON.")
    st.stop()

fc_grids, fc_farms = split_feature_collections(fc_all)

show_grids = st.sidebar.checkbox("Show grid rectangles", value=True)
show_farms = st.sidebar.checkbox("Show farm polygons", value=True)

# ----------------------------- MAP INIT --------------------------------------
# Prefer overall bounds; fallback to India center
bounds_all = features_bounds(fc_all.get("features", []))
center_latlon = center_from_bounds(bounds_all) if bounds_all else [20.5937, 78.9629]

m = folium.Map(location=center_latlon, zoom_start=11, tiles=None)

# Satellite base + labels overlay
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr=("Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, "
          "CNES/Airbus DS, USDA, USGS, AeroGRID, IGN, and the GIS User Community"),
    name="Satellite",
    control=True,
).add_to(m)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    attr="© Esri",
    name="Labels",
    overlay=True,
    control=True,
    opacity=0.75,
).add_to(m)

# Map utilities
MiniMap(toggle_display=True).add_to(m)
Fullscreen().add_to(m)
MeasureControl(primary_length_unit="meters", secondary_length_unit="kilometers").add_to(m)
MousePosition(
    position="bottomright",
    separator=" | ",
    empty_string="",
    lng_first=True,
    num_digits=5,
    prefix="Lon,Lat:"
).add_to(m)

# ----------------------------- LAYERS ----------------------------------------
if show_grids and fc_grids["features"]:
    grids = folium.GeoJson(
        data=fc_grids,
        name="Grids",
        style_function=grid_style,
        tooltip=folium.GeoJsonTooltip(
            fields=["Grid ID", "Farms in this grid", "Grid Lat,Lon", "name"],
            aliases=["Grid ID", "Farms", "Lat,Lon", "Name"],
            sticky=False,
        ),
        popup=folium.GeoJsonPopup(
            fields=["Grid ID", "Grid Lat,Lon", "Farms in this grid", "name"],
            aliases=["Grid ID", "Lat,Lon", "Farms in grid", "Name"],
            localize=True,
            labels=True,
            parse_html=True,
            max_width=420,
        ),
    )
    grids.add_to(m)

if show_farms and fc_farms["features"]:
    farms = folium.GeoJson(
        data=fc_farms,
        name="Farms",
        style_function=farm_style,
        tooltip=folium.GeoJsonTooltip(
            fields=["Farmer Name", "Farmer ID", "Village", "Cluster", "Intercrop"],
            aliases=["Farmer", "ID", "Village", "Cluster", "Intercrop"],
            sticky=False,
        ),
        popup=folium.GeoJsonPopup(
            fields=["Farmer Name", "Farmer ID", "Village", "Cluster", "Cotton sowing date", "Intercrop"],
            aliases=["Farmer Name", "Farmer ID", "Village", "Cluster", "Cotton sowing date", "Intercrop"],
            localize=True,
            labels=True,
            parse_html=True,
            max_width=420,
        ),
    )
    farms.add_to(m)

# Fit bounds
if bounds_all:
    sw = [bounds_all[0][0], bounds_all[0][1]]
    ne = [bounds_all[1][0], bounds_all[1][1]]
    try:
        m.fit_bounds([sw, ne], padding=(20, 20))
    except Exception:
        pass

folium.LayerControl(collapsed=False).add_to(m)

# ----------------------------- RENDER ----------------------------------------
st.markdown(
    f"### Map: `{selected_file}`  \n"
    "Hover for tooltips. Click a **grid** for grid info, or a **farm polygon** for farmer info."
)
st_folium(m, height=640, use_container_width=True)
