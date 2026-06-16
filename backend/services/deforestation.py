import numpy as np
import rasterio
import geopandas as gpd
import matplotlib.pyplot as plt

from scipy.ndimage import binary_opening, binary_closing
from skimage.measure import label, regionprops
from rasterio.features import shapes
from shapely.geometry import shape
from rasterio.features import shapes
import psycopg2

from sqlalchemy import create_engine
from datetime import date



def compute_features(img):
    """
    Expected band order:
    [Blue, Green, Red, RedEdge, NIR, SWIR1, SWIR2]

    Output shape:
    (H, W, 9)
    """
    with rasterio.open(img) as src:
        blue = src.read(1).astype("float32")
        green = src.read(2).astype("float32")
        red = src.read(3).astype("float32")
        re1 = src.read(4).astype("float32")
        nir = src.read(7).astype("float32")
        swir1 = src.read(9).astype("float32")
        swir2 = src.read(10).astype("float32")

    # Normalize reflectance
    bluef  = blue / 10000
    greenf = green / 10000
    redf   = red / 10000
    re1f   = re1 / 10000
    nirf   = nir / 10000
    swir1f = swir1 / 10000
    swir2f = swir2 / 10000

    eps = 1e-9

    # Spectral indices
    ndvi = (nirf - redf) / (nirf + redf + eps)
    ndre = (nirf - re1f) / (nirf + re1f + eps)
    ndmi = (nirf - swir1f) / (nirf + swir1f + eps)
    nbr  = (nirf - swir2f) / (nirf + swir2f + eps)
    evi  = 2.5 * (nirf - redf) / (nirf + 6*redf - 7.5*bluef + 1 + eps)

    # Floating Algae Index (you used this in training)
    lambda_red = 665
    lambda_nir = 842
    lambda_swir1 = 1610

    nir_baseline = redf + (swir1f - redf) * (
        (lambda_nir - lambda_red) / (lambda_swir1 - lambda_red)
    )
    fai = nirf - nir_baseline

    # Final feature stack for RF
    feature_stack = np.stack(
        [re1f, nirf, swir1f],
        axis=-1
    )
    # print("Feature stack shape:", feature_stack.shape)
    # print("Feature mins:", np.min(feature_stack, axis=(0,1)))
    # print("Feature maxs:", np.max(feature_stack, axis=(0,1)))
    return feature_stack


# ============================================================
# 2. RF PREDICTION
# ============================================================
def predict_vegetation_mask(tif_path, model):
    with rasterio.open(tif_path) as src:
        img = src.read()

    features = compute_features(tif_path)
    h, w, n_features = features.shape

    # reshape correctly
    X = features.reshape(-1, n_features)
    
    # VALID PIXELS ONLY (same as your manual code)
    valid = np.all(np.isfinite(X), axis=1)
    # print("Total pixels:", X.shape[0])
    # print("Valid pixels:", np.sum(valid))
    # initialize prediction
    pred_flat = np.zeros(X.shape[0], dtype=np.uint8)

    # predict ONLY valid pixels
    pred_flat[valid] = model.predict(X)

    # reshape back
    mask = pred_flat.reshape(h, w)

    return mask, img


# ============================================================
# 3. RAW DEFORESTATION
# ============================================================
def get_raw_deforestation(before_mask, after_mask):
    """
    Deforestation = vegetation before AND not vegetation after
    """
    return ((before_mask == 1) & (after_mask == 0)).astype(np.uint8)


# ============================================================
# 4. CLEAN MASK
# ============================================================
def clean_deforestation_mask(raw_mask, open_size=3, close_size=5):
    clean = binary_opening(raw_mask, structure=np.ones((open_size, open_size)))
    clean = binary_closing(clean, structure=np.ones((close_size, close_size)))
    return clean.astype(np.uint8)


# ============================================================
# 5. REMOVE SMALL PATCHES
# ============================================================
def remove_small_patches(mask, min_patch_pixels=100):
    labeled = label(mask)
    regions = regionprops(labeled)

    filtered = np.zeros_like(mask, dtype=np.uint8)

    for region in regions:
        if region.area >= min_patch_pixels:
            filtered[labeled == region.label] = 1

    return filtered


def save_mask_as_tif(reference_path, mask, output_path):
    with rasterio.open(reference_path) as src:
        profile = src.profile.copy()

        profile.update(
            dtype=rasterio.uint8,
            count=1,
            compress='lzw',
            nodata=0
        )

        mask_to_save = (mask.astype(np.uint8) * 255)

        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(mask_to_save, 1)



# ============================================================
# 6. MAIN DEBUG FUNCTION
# ============================================================
def detect_deforestation(
    before_path,
    after_path,
    model,
    min_patch_pixels=100,
    open_size=3,
    close_size=5,
):
    """
    Detect deforestation between before and after TIFFs.

    For now:
    - NO polygon conversion
    - NO saving
    - ONLY visualization + masks

    Returns:
    - before_mask
    - after_mask
    - raw_deforestation
    - filtered_mask
    """

    # Step 1: Predict vegetation masks
    before_mask, before_img = predict_vegetation_mask(before_path, model)
    after_mask, after_img = predict_vegetation_mask(after_path, model)

    # Step 2: Detect raw vegetation loss
    raw_deforestation = get_raw_deforestation(before_mask, after_mask)

    # Step 3: Clean noise
    clean_mask = clean_deforestation_mask(raw_deforestation, open_size, close_size)

    # Step 4: Remove tiny patches
    filtered_mask = remove_small_patches(clean_mask, min_patch_pixels=min_patch_pixels)
    # Step 6: Save outputs
    save_mask_as_tif(before_path, raw_deforestation, "raw_deforestation.tif")
    save_mask_as_tif(before_path, filtered_mask, "clean_deforestation.tif")

    before_rgb = np.dstack([before_img[2], before_img[1], before_img[0]])
    before_rgb = before_rgb / np.percentile(before_rgb, 98)
    before_rgb = np.clip(before_rgb, 0, 1)


    after_rgb  = np.dstack([after_img[2], after_img[1], after_img[0]])
    after_rgb  = after_rgb / np.percentile(after_rgb, 98)
    after_rgb  = np.clip(after_rgb, 0, 1)

    overlay = after_rgb.copy()
    overlay[filtered_mask == 1] = [1, 0, 0]
    # Step 5: Visualize
    """
    if visualize:
        before_rgb = np.dstack([before_img[2], before_img[1], before_img[0]])
        after_rgb  = np.dstack([after_img[2], after_img[1], after_img[0]])

        # simple contrast stretch
        before_rgb = before_rgb / np.percentile(before_rgb, 98)
        after_rgb  = after_rgb / np.percentile(after_rgb, 98)

        before_rgb = np.clip(before_rgb, 0, 1)
        after_rgb  = np.clip(after_rgb, 0, 1)

        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        
    
        axes[0, 0].imshow(before_rgb)
        axes[0, 0].set_title("Before RGB")
        axes[0, 0].axis("off")

        axes[0, 1].imshow(before_mask, cmap="Greens")
        axes[0, 1].set_title("Before Vegetation Mask")
        axes[0, 1].axis("off")

        axes[0, 2].imshow(after_rgb)
        axes[0, 2].set_title("After RGB")
        axes[0, 2].axis("off")

        axes[1, 0].imshow(after_mask, cmap="Greens")
        axes[1, 0].set_title("After Vegetation Mask")
        axes[1, 0].axis("off")

        axes[1, 1].imshow(raw_deforestation, cmap="Reds")
        axes[1, 1].set_title("Raw Deforestation")
        axes[1, 1].axis("off")

        axes[1, 2].imshow(filtered_mask, cmap="Reds")
        axes[1, 2].set_title("Cleaned Deforestation")
        axes[1, 2].axis("off")

        plt.tight_layout()
        plt.show()
    """

    return before_rgb, after_rgb, before_mask, after_mask, overlay, filtered_mask


def mask_to_polygons(reference_tif_path, filtered_mask):
    """
    Convert binary mask to polygons using raster georeferencing.
    Returns a GeoDataFrame.
    """

    with rasterio.open(reference_tif_path) as src:
        transform = src.transform
        crs = src.crs

    polygons = []

    for geom, value in shapes(
        filtered_mask.astype("uint8"),
        mask=filtered_mask.astype(bool),
        transform=transform
    ):
        if value == 1:
            polygons.append(shape(geom))

    gdf = gpd.GeoDataFrame(geometry=polygons, crs=crs)

    return gdf

def insert_deforestation_to_postgis(deforestation_gdf, detected_at):
    """
    Insert deforestation polygons into existing PostGIS table:
    detected_deforestation(geometry, detected_at)
    """

    # 1. Convert CRS to EPSG:4326 because your table expects that
    gdf = deforestation_gdf.to_crs(epsg=4326).copy()

    # 2. Add detected date
    gdf["detected_at"] = detected_at

    # 3. Keep only columns that exist in your table
    gdf = gdf[["geometry", "detected_at"]]

    # 4. PostgreSQL connection
    engine = create_engine(
    "postgresql+psycopg2://rajlaxmiawatade@localhost:5432/FinalYearProject"
    )

    # 5. Insert into PostGIS table
    gdf.to_postgis(
        name="detected_deforestation",
        con=engine,
        if_exists="append",
        index=False
    )

    print(f"Inserted {len(gdf)} polygons into detected_deforestation")