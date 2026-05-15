import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
from geopy.geocoders import Nominatim
import math
import rasterio
import numpy as np
from PIL import Image

from datetime import datetime

def format_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y%m%d").strftime("%d %b %Y")
    except:
        return date_str
    
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

from components.navbar import show_navbar
from components.footer import show_footer

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(layout="wide")



if "coords" not in st.session_state:
    st.session_state.coords = (22.5937, 78.9629)

if "lat" not in st.session_state:
    st.session_state.lat = ""

if "lon" not in st.session_state:
    st.session_state.lon = ""

if "location_name" not in st.session_state:
    st.session_state.location_name = ""

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

# -------------------------------
# 🧠 UNIVERSAL IMAGE LOADER
# -------------------------------
import requests
from io import BytesIO

import base64
from io import BytesIO
import requests
import rasterio
import numpy as np
from PIL import Image
import streamlit as st

def load_image(source):
    try:
        # ✅ Case 1: Base64 image (NEW 🔥)
        if isinstance(source, str) and len(source) > 1000:
            img_bytes = base64.b64decode(source)
            img = Image.open(BytesIO(img_bytes))
            return img

        # ✅ Case 2: URL image
        elif str(source).startswith("http"):
            response = requests.get(source)
            img = Image.open(BytesIO(response.content))
            return img

        # ✅ Case 3: TIF file
        elif str(source).endswith(".tif"):
            with rasterio.open(source) as src:
                red = src.read(4)
                green = src.read(3)
                blue = src.read(2)

                red = red / 10000
                green = green / 10000
                blue = blue / 10000

                rgb = np.stack([red, green, blue], axis=-1)
                rgb = (rgb - np.min(rgb)) / (np.max(rgb) - np.min(rgb))

                return rgb

        # ✅ Case 4: Normal image file
        else:
            return Image.open(source)

    except Exception as e:
        st.error(f"Error loading image: {e}")
        return None
# -------------------------------
# NAVBAR
# -------------------------------
show_navbar(st.session_state.role)

# -------------------------------
# TITLE
# -------------------------------
st.markdown("<h3 style='text-align:center;'>🗺 Select Area (Draw Box)</h3>", unsafe_allow_html=True)

tile_option = st.selectbox("Map Type", ["Satellite", "Street"])

lat_val, lon_val = st.session_state.coords

# -------------------------------
# BASE MAP
# -------------------------------
m = folium.Map(
    location=[lat_val, lon_val],
    zoom_start=5 if st.session_state.coords == (22.5937, 78.9629) else 15,
    tiles=None
)

# -------------------------------
# TILE LAYERS
# -------------------------------
if tile_option == "Satellite":
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Satellite",
    ).add_to(m)

    folium.TileLayer(
        tiles="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Labels",
    ).add_to(m)
else:
    folium.TileLayer("OpenStreetMap").add_to(m)

# -------------------------------
# DRAW TOOL
# -------------------------------
Draw(
    draw_options={
        "rectangle": True,
        "polygon": True,
        "circle": False,
        "marker": False,
        "polyline": False,
        "circlemarker": False,
    },
    edit_options={"edit": False}
).add_to(m)

# -------------------------------
# CENTER MAP
# -------------------------------
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    map_data = st_folium(m, height=600, width=600)

# -------------------------------
# HANDLE DRAW
# -------------------------------
if map_data and map_data.get("all_drawings"):

    shape = map_data["all_drawings"][-1]
    coords = shape["geometry"]["coordinates"][0]

    lats = [pt[1] for pt in coords]
    lons = [pt[0] for pt in coords]

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    st.session_state.coords = (center_lat, center_lon)
    st.session_state.lat = round(center_lat, 6)
    st.session_state.lon = round(center_lon, 6)

    # Reverse geocoding
    try:
        geolocator = Nominatim(user_agent="greenguard")
        location = geolocator.reverse((center_lat, center_lon), timeout=5)

        if location:
            st.session_state.location_name = location.address.split(",")[0]
    except:
        st.session_state.location_name = "Unknown Location"

    # 4km box
    delta_lat = 2 / 111
    delta_lon = 2 / (111 * math.cos(math.radians(center_lat)))

    bounds = [
        [center_lat - delta_lat, center_lon - delta_lon],
        [center_lat + delta_lat, center_lon + delta_lon]
    ]

    zoom_map = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles=None)

    if tile_option == "Satellite":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri Satellite",
        ).add_to(zoom_map)
    else:
        folium.TileLayer("OpenStreetMap").add_to(zoom_map)

    folium.Rectangle(bounds=bounds, color="green", fill=True, fill_opacity=0.2).add_to(zoom_map)

    folium.Marker([center_lat, center_lon], tooltip="Center").add_to(zoom_map)

    st.markdown("### 🔍 Selected 4km × 4km Area")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st_folium(zoom_map, height=600, width=600)

# -------------------------------
# LOCATION DETAILS
# -------------------------------
st.markdown("## 📍 Location Details")

col1, col2, col3 = st.columns(3)

location_name = col1.text_input("Location", value=st.session_state.location_name)
lat = col2.text_input("Latitude", value=st.session_state.lat)
lon = col3.text_input("Longitude", value=st.session_state.lon)

# -------------------------------
# ANALYZE BUTTON
# -------------------------------
center = st.columns([2,1,2])

with center[1]:
    if st.button("🚀 Analyze", use_container_width=True):

        try:
            lat_val = float(lat)
            lon_val = float(lon)

            st.success(f"📍 Location: {lat_val}, {lon_val}")

            # -------------------------------
            # BACKEND READY STRUCTURE
            # -------------------------------
            from utils.api import analyze_location

            result = analyze_location(lat_val, lon_val)

            st.session_state.analysis_result = result

        except:
            st.error("❌ Invalid coordinates")

# -------------------------------
# RESULT CARDS
# -------------------------------
if st.session_state.analysis_result:

    res = st.session_state.analysis_result

    st.markdown("## 📊 Analysis Results")

    c1, c2, c3, c4 = st.columns(4, gap="large")

    with c1:
        with st.container(border=True):
            st.markdown("🌿 **Green Cover Loss**")
            st.markdown(f"### {res['green_cover_loss']} %")

    with c2:
        with st.container(border=True):
            st.markdown("🚫 **Illegal Area Loss**")
            st.markdown(f"### {res['illegal_area_loss']} km²")

    with c3:
        with st.container(border=True):
            st.markdown("📜 **Legal Deforestation**")
            st.markdown(f"### {res['legal_deforestation']} km²")

    with c4:
        with st.container(border=True):
            st.markdown("📉 **NDVI Loss**")
            st.markdown(f"### {res['ndvi_loss']}")

# -------------------------------
# 🛰 BEFORE & AFTER IMAGES
# -------------------------------
if st.session_state.analysis_result:

    res = st.session_state.analysis_result

    st.markdown("## 🛰 Before vs After Satellite View")

    before_img = load_image(res["before_image"])
    after_img = load_image(res["after_image"])

    before_date = format_date(res.get("before_date", "N/A"))
    after_date = format_date(res.get("after_date", "N/A"))

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"### 📅 Before ({before_date})")
        if before_img is not None:
            st.image(before_img, width='stretch')

    with col2:
        st.markdown(f"### 📅 After ({after_date})")
        if after_img is not None:
            st.image(after_img, width='stretch')
# -------------------------------

# -------------------------------
# 🌲 DEFORESTATION OVERLAY
# -------------------------------
if st.session_state.analysis_result:

    res = st.session_state.analysis_result

    st.markdown("## 🌲 Deforestation Map")

    overlay_path = res.get("overlay_image")

    if overlay_path:

        overlay_img = load_image(overlay_path)

        if overlay_img is not None:
            col1, col2, col3 = st.columns([1, 2, 1])

            with col2:
                st.image(overlay_img, width=500)

        else:
            st.error("❌ Overlay image not loading")

    else:
        st.error("❌ Overlay path missing from backend")


# -------------------------------
# 🚫 TOP 5 ILLEGAL POLYGONS
# -------------------------------
if st.session_state.analysis_result:

    st.markdown("## 🚫 Top Illegal Deforested Polygons")

    res = st.session_state.analysis_result

    # -------------------------------
    # 🔗 BACKEND DATA (replace later)
    # -------------------------------
    illegal_polygons = res.get("illegal_polygons", [
        {"id": "P1", "area": 2.5, "centroid": [73.88, 18.58]},
        {"id": "P2", "area": 2.1, "centroid": [73.89, 18.57]},
        {"id": "P3", "area": 1.9, "centroid": [73.87, 18.56]},
        {"id": "P4", "area": 1.5, "centroid": [73.86, 18.55]},
        {"id": "P5", "area": 1.2, "centroid": [73.85, 18.54]},
        {"id": "P6", "area": 0.9, "centroid": [73.84, 18.53]},
    ])

    # -------------------------------
    # 🔽 SORT DESC (IMPORTANT)
    # -------------------------------
    illegal_polygons = sorted(illegal_polygons, key=lambda x: x["area"], reverse=True)

    top5 = illegal_polygons[:5]

    for poly in top5:
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)

            c1.markdown(f"**🆔 ID:** {poly['id']}")
            c2.markdown(f"**📏 Area:** {round(poly['area'], 2)} km²")
            c3.markdown(f"**📍 Centroid:** {poly['centroid']}")

# -------------------------------
# 📄 GENERATE FULL REPORT
# -------------------------------

if st.session_state.analysis_result:

    if st.button("📄 Generate Full Report"):

        st.markdown("## 📄 Full Illegal Deforestation Report")

        full_report = illegal_polygons  # later → API call

        for poly in full_report:
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)

                c1.markdown(f"**🆔 ID:** {poly['id']}")
                c2.markdown(f"**📏 Area:** {round(poly['area'], 2)} km²")
                c3.markdown(f"**📍 Centroid:** {poly['centroid']}")