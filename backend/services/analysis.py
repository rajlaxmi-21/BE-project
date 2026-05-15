from db import get_connection
import random

from services.image_fetch import fetch_images
from utils.image_utils import convert_to_png
import base64

from services.deforestation import (
    detect_deforestation,
    create_overlay_image,
    save_rgb_image
)
import os

def encode_image(path):
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode("utf-8")

from services.image_fetch import fetch_images
from services.deforestation import detect_deforestation, create_overlay_image
import os

SAVE_PATH = "C:/Users/Shreya/Desktop/results"

def analyze_area(lat, lon):

    os.makedirs(SAVE_PATH, exist_ok=True)

    # MODULE 1
    images = fetch_images(lat, lon)

    before_path = images["previous"]
    after_path = images["current"]

    # ✅ ADD THESE (fetch from images dict)
    before_date = images.get("previous_date")
    after_date = images.get("current_date")

    # MODULE 2
    rgb_before, rgb_after, mask = detect_deforestation(before_path, after_path)

    overlay_path = os.path.join(SAVE_PATH, "overlay.png")
    create_overlay_image(rgb_after, mask, overlay_path)

    before_path = os.path.join(SAVE_PATH, "before.png")
    after_path = os.path.join(SAVE_PATH, "after.png")

    save_rgb_image(rgb_before, before_path)
    save_rgb_image(rgb_after, after_path)

    return {
        "green_cover_loss": 12.5,
        "illegal_area_loss": 2.3,
        "legal_deforestation": 1.1,
        "ndvi_loss": 0.23,

        "before_image": before_path,
        "after_image": after_path,
        "overlay_image": overlay_path,

        # ✅ NEW
        "before_date": before_date,
        "after_date": after_date
    }

def save_detection(polygon_wkt):
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = """
        INSERT INTO detected_deforestation (geometry, detected_at)
        VALUES (ST_GeomFromText(%s, 4326), CURRENT_DATE)
        """

        cur.execute(query, (polygon_wkt,))
        conn.commit()

        cur.close()
        conn.close()

    except Exception as e:
        print("DB Error:", e)