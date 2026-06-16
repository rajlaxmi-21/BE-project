import base64
import os
import joblib
from datetime import date
from services.image_fetch import fetch_images

from services.deforestation import (
    detect_deforestation,
    mask_to_polygons,
    insert_deforestation_to_postgis
)

from services.verification import (
    verify_deforestation_against_permits,
    calculate_summary_stats,
    get_top_illegal_polygons
)
from io import BytesIO
from PIL import Image
import base64
import numpy as np


SAVE_PATH = "/Users/rajlaxmiawatade/Desktop/results"

MODEL_PATH = "model/model.pkl"
model = joblib.load(MODEL_PATH)

def array_to_base64(arr):

    if arr.dtype != np.uint8:
        arr = (arr * 255).astype(np.uint8)

    img = Image.fromarray(arr)

    buffer = BytesIO()
    img.save(buffer, format="PNG")

    return base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")



def analyze_area(lat, lon):

    os.makedirs(SAVE_PATH, exist_ok=True)

    # MODULE 1
    images = fetch_images(lat, lon)

    before_path = images["previous"]
    after_path = images["current"]

    before_date = images.get("previous_date")
    after_date = images.get("current_date")

    # MODULE 2
    before_rgb, after_rgb, before_mask, after_mask, overlay, filtered_mask = detect_deforestation(
        before_path,
        after_path,
        model,
        min_patch_pixels=5  
    )

    # ----------------------------------------
    # MASK → POLYGONS
    # ----------------------------------------
    deforestation_gdf = mask_to_polygons(before_path, filtered_mask)
    insert_deforestation_to_postgis(deforestation_gdf, date.today())

    verify_deforestation_against_permits()

    stats = calculate_summary_stats()
    illegal_polygons = get_top_illegal_polygons()

    return_obj = {
        "before_rgb": array_to_base64(before_rgb),
        "after_rgb": array_to_base64(after_rgb),
        "overlay": array_to_base64(overlay),
       # "before_veg_mask_tif": before_mask,
       # "after_veg_mask_tif": after_mask,
       # "loss_mask": filtered_mask,
        "total_green_cover_loss_km2": stats["total_green_cover_loss_km2"],
        "illegal_area_km2": stats["illegal_area_km2"],
        "legal_area_km2": stats["legal_area_km2"],
        "total_legal_deforestation_count": stats["total_legal_deforestation_count"],
        "before_date": before_date,
        "after_date": after_date,
        "illegal_polygons": illegal_polygons
    }

    return return_obj



