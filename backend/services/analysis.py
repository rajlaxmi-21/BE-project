from db import get_connection
import base64
import os

from services.image_fetch import fetch_images

from services.deforestation import (
    detect_deforestation,
    save_rgb_image,
    save_mask_image,
    mask_to_polygons,
    insert_deforestation_to_postgis
)

SAVE_PATH = "C:/Users/Shreya/Desktop/results"


def encode_image(path):

    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode("utf-8")


def analyze_area(lat, lon):

    os.makedirs(SAVE_PATH, exist_ok=True)

    # MODULE 1
    images = fetch_images(lat, lon)

    before_path = images["previous"]
    after_path = images["current"]

    before_date = images.get("previous_date")
    after_date = images.get("current_date")

    # MODULE 2
    rgb_before, rgb_after, mask, original_mask = detect_deforestation(
        before_path,
        after_path
    )

    # ----------------------------------------
    # MASK → POLYGONS
    # ----------------------------------------
    gdf = mask_to_polygons(before_path, original_mask)

    # Save into PostGIS
    insert_deforestation_to_postgis(gdf)

    # Save mask visualization
    mask_path = os.path.join(SAVE_PATH, "deforestation_mask.png")

    save_mask_image(rgb_after, mask, mask_path)

    # Save RGB images
    before_img_path = os.path.join(SAVE_PATH, "before.png")
    after_img_path = os.path.join(SAVE_PATH, "after.png")

    save_rgb_image(rgb_before, before_img_path)
    save_rgb_image(rgb_after, after_img_path)

    return {

        "green_cover_loss": 12.5,
        "illegal_area_loss": 2.3,
        "legal_deforestation": 1.1,
        "ndvi_loss": 0.23,

        "before_image": before_img_path,
        "after_image": after_img_path,
        "overlay_image": mask_path,

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