import rasterio
import numpy as np
import joblib
from PIL import Image
from scipy.ndimage import (
    binary_opening,
    binary_closing,
    binary_dilation
)

# -------------------------------
# LOAD MODEL
# -------------------------------
MODEL_PATH = "model/model.pkl"
model = joblib.load(MODEL_PATH)

# -------------------------------
# RESIZE FUNCTION (NO CV2)
# -------------------------------
def resize_image(img, scale=0.4):

    h, w = img.shape[:2]
    new_size = (int(w * scale), int(h * scale))

    # Convert to uint8 for PIL
    if img.dtype != np.uint8:
        img_temp = (img * 255).astype(np.uint8)
    else:
        img_temp = img

    img_pil = Image.fromarray(img_temp)
    img_resized = img_pil.resize(new_size, Image.BILINEAR)

    # Convert back to float [0,1]
    if len(img.shape) == 3:
        return np.array(img_resized) / 255.0
    else:
        return np.array(img_resized)

# -------------------------------
# CONVERT TO UINT8
# -------------------------------
def to_uint8(img):
    return (img * 255).astype(np.uint8)

# -------------------------------
# LOAD BANDS + NORMALIZATION
# -------------------------------
def load_bands(path):

    with rasterio.open(path) as src:

        # NDVI bands
        red = src.read(4).astype(np.float32)
        nir = src.read(8).astype(np.float32)

        # RGB bands
        r = src.read(3).astype(np.float32)
        g = src.read(2).astype(np.float32)
        b = src.read(1).astype(np.float32)

        # Stack RGB
        rgb = np.stack([r, g, b], axis=-1)

        # -------------------------------
        # NORMALIZATION
        # -------------------------------

        # Percentile stretch
        p2 = np.percentile(rgb, 2)
        p98 = np.percentile(rgb, 98)

        rgb = (rgb - p2) / (p98 - p2)

        # Clip values
        rgb = np.clip(rgb, 0, 1)

        # Slight gamma correction
        rgb = rgb ** 0.9

    return red, nir, rgb

# -------------------------------
# NDVI
# -------------------------------
def compute_ndvi(nir, red):

    return (nir - red) / (nir + red + 1e-6)

# -------------------------------
# FEATURES
# -------------------------------
def create_features(ndvi_before, ndvi_after):

    diff = ndvi_before - ndvi_after

    features = np.stack([
        ndvi_before.flatten(),
        ndvi_after.flatten(),
        diff.flatten()
    ], axis=1)

    return features

# -------------------------------
# BATCH PREDICTION
# -------------------------------
def predict_in_batches(model, features, batch_size=50000):

    preds = []

    for i in range(0, len(features), batch_size):

        batch = features[i:i+batch_size]
        pred = model.predict(batch)

        preds.append(pred)

    return np.concatenate(preds)

# -------------------------------
# MAIN FUNCTION
# -------------------------------
def detect_deforestation(before_path, after_path):

    red_b, nir_b, rgb_before = load_bands(before_path)
    red_a, nir_a, rgb_after = load_bands(after_path)

    # NDVI
    ndvi_b = compute_ndvi(nir_b, red_b)
    ndvi_a = compute_ndvi(nir_a, red_a)

    # Features
    features = create_features(ndvi_b, ndvi_a)

    # Predictions
    preds = predict_in_batches(model, features)

    mask = preds.reshape(ndvi_b.shape)

    # -------------------------------
    # CLEAN MASK
    # -------------------------------
    mask = binary_opening(mask, structure=np.ones((3,3)))
    mask = binary_closing(mask, structure=np.ones((5,5)))

    # Keep only vegetation loss
    diff = ndvi_b - ndvi_a

    mask = np.logical_and(mask == 1, diff > 0.1)

    # -------------------------------
    # RESIZE
    # -------------------------------
    rgb_before = resize_image(rgb_before)
    rgb_after = resize_image(rgb_after)

    mask = resize_image(mask.astype(np.uint8))

    return rgb_before, rgb_after, mask

# -------------------------------
# OVERLAY IMAGE
# -------------------------------
def create_overlay_image(rgb, mask, save_path):

    # Make regions thicker
    mask = binary_dilation(mask, structure=np.ones((4,4)))

    overlay = rgb.copy()

    # -------------------------------
    # BRIGHT RED REGIONS
    # -------------------------------
    overlay[mask == 1] = [1, 0, 0]

    # Convert to uint8
    overlay = (overlay * 255).astype(np.uint8)

    # Save
    Image.fromarray(overlay).save(save_path)

    return save_path

# -------------------------------
# SAVE NORMALIZED RGB IMAGE
# -------------------------------
def save_rgb_image(rgb, save_path):

    img = (rgb * 255).astype(np.uint8)

    Image.fromarray(img).save(save_path)

    return save_path