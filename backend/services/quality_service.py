"""Quality assessment and document cleaning service for Doc Scanner.

Follows the DOC SCANNER capture & quality specification:
Step B. EXIF orientation correction.
Step C. Check copy resized to 640 px long edge for fast sub-second analysis.
Step D. Corner detection (quadrilateral finding, cut-off edge detection).
Step E. Metrics measured on page area only (warped page):
        - Tile Laplacian variance (70th-75th percentile of 8x8 grid tiles)
        - Mean brightness (0-255)
        - Glare percentage (> 250 RGB saturated specular pixels)
        - Coverage (page area / frame area)
Step F. Single clear reason according to specification table.
Step G. Straighten & enhance (perspective warp, grayscale, CLAHE, 1568 px, JPEG Q80 < 1MB).
"""

import os
import io
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
import cv2
from PIL import Image, ImageOps

logger = logging.getLogger("i2i.quality")

# Environment Thresholds (spec default values)
DEFAULT_BLUR_MIN = float(os.getenv("QUALITY_BLUR_MIN", "40.0"))
DEFAULT_DARK_MAX = float(os.getenv("QUALITY_DARK_MAX", "75.0"))
DEFAULT_GLARE_MAX = float(os.getenv("QUALITY_GLARE_MAX", "12.0"))
DEFAULT_COVER_MIN = float(os.getenv("QUALITY_COVER_MIN", "60.0"))

# Spec Messages
MSG_CHECK_FAILED = "We could not check this photo. Retake if you are unsure."
MSG_CORNERS_NOT_FOUND = "Move the whole page into the frame."
MSG_COVERAGE_LOW = "Move closer so the page fills the screen."
MSG_TOO_DARK = "It's too dark. Turn on the light or move to a brighter place."
MSG_GLARE = "There is glare on the page. Tilt the phone slightly."
MSG_BLURRY = "The photo is blurry. Hold the phone still and tap to focus."


def get_quality_config() -> Dict[str, float]:
    """Retrieve active quality thresholds from environment."""
    return {
        "blur_min": float(os.getenv("QUALITY_BLUR_MIN", "40.0")),
        "dark_max": float(os.getenv("QUALITY_DARK_MAX", "75.0")),
        "glare_max": float(os.getenv("QUALITY_GLARE_MAX", "12.0")),
        "cover_min": float(os.getenv("QUALITY_COVER_MIN", "60.0")),
    }


def order_points(pts: np.ndarray) -> np.ndarray:
    """Order coordinates in consistent order: [top-left, top-right, bottom-right, bottom-left]."""
    pts = pts.reshape(4, 2).astype(np.float32)
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]       # top-left has minimum x + y
    rect[2] = pts[np.argmax(s)]       # bottom-right has maximum x + y
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]    # top-right has minimum y - x
    rect[3] = pts[np.argmax(diff)]    # bottom-left has maximum y - x
    return rect


def warp_perspective(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Warp quadrilateral region to a flat upright rectangle."""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    max_w = max(2, int(round(max(width_top, width_bottom))))

    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)
    max_h = max(2, int(round(max(height_left, height_right))))

    dst = np.array([
        [0, 0],
        [max_w - 1, 0],
        [max_w - 1, max_h - 1],
        [0, max_h - 1]
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (max_w, max_h), flags=cv2.INTER_LINEAR)
    return warped


def detect_page_corners(img: np.ndarray) -> Tuple[Optional[np.ndarray], float, Optional[str]]:
    """Detect the 4 corners of the form sheet in the frame.

    Returns:
        (corners, coverage_pct, issue_msg)
        - corners: (4, 2) array of coordinates, or None if not found / cut off
        - coverage_pct: estimated percentage of frame occupied by the page (0.0 to 100.0)
        - issue_msg: MSG_CORNERS_NOT_FOUND or None
    """
    h, w = img.shape[:2]
    total_area = float(h * w)
    if total_area <= 0:
        return None, 0.0, MSG_CORNERS_NOT_FOUND

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img

    # Check if image is already a full-frame scan (document fills entire frame, corners near white/document)
    corner_inset = min(15, h // 10, w // 10)
    c_tl = np.mean(gray[:corner_inset, :corner_inset])
    c_tr = np.mean(gray[:corner_inset, -corner_inset:])
    c_bl = np.mean(gray[-corner_inset:, :corner_inset])
    c_br = np.mean(gray[-corner_inset:, -corner_inset:])
    all_corners_bright = (c_tl > 165 and c_tr > 165 and c_bl > 165 and c_br > 165)

    # Blur to reduce high-frequency texture
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Edge and threshold masks
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edges = cv2.Canny(blurred, 30, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges_dilated = cv2.dilate(edges, kernel)

    best_candidate = None
    best_area = 0.0
    best_coverage = 0.0
    is_cut_off = False

    for mask in [thresh, edges_dilated]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for c in contours[:5]:
            area = cv2.contourArea(c)
            cov = (area / total_area) * 100.0
            if cov < 15.0:
                continue

            pts = c.reshape(-1, 2)
            margin = max(3, int(min(w, h) * 0.01))
            touches_left = np.sum(pts[:, 0] <= margin) > 8
            touches_right = np.sum(pts[:, 0] >= w - 1 - margin) > 8
            touches_top = np.sum(pts[:, 1] <= margin) > 8
            touches_bottom = np.sum(pts[:, 1] >= h - 1 - margin) > 8
            num_touches = sum([touches_left, touches_right, touches_top, touches_bottom])

            # If it touches 1, 2, or 3 borders while background is present, it is cut off at the edge
            if 1 <= num_touches <= 3 and cov < 90.0:
                is_cut_off = True
                best_coverage = max(best_coverage, cov)
                continue

            hull = cv2.convexHull(c)
            peri = cv2.arcLength(hull, True)
            if peri <= 0:
                continue

            for factor in np.linspace(0.01, 0.08, 30):
                approx = cv2.approxPolyDP(hull, factor * peri, True)
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    if area > best_area:
                        best_area = area
                        best_coverage = cov
                        best_candidate = approx.reshape(4, 2).astype(np.float32)
                    break

        if best_candidate is not None:
            break

    if best_candidate is not None:
        return order_points(best_candidate), round(best_coverage, 1), None

    if is_cut_off:
        return None, round(best_coverage, 1), MSG_CORNERS_NOT_FOUND

    # If all 4 image corners are bright and frame appears to be document throughout
    if all_corners_bright and np.mean(gray) > 135:
        full_corners = np.array([
            [0, 0],
            [w - 1, 0],
            [w - 1, h - 1],
            [0, h - 1]
        ], dtype=np.float32)
        return full_corners, 100.0, None

    return None, round(best_coverage, 1), MSG_CORNERS_NOT_FOUND


def compute_tile_laplacian_variance(gray_array: np.ndarray, grid_size: int = 8, percentile: float = 75.0) -> float:
    """Compute Laplacian variance over a grid of tiles and return high percentile.

    Using the 60th-75th percentile ensures blank margins and white borders
    do not drag down the sharpness score of handwritten or printed text.
    """
    h, w = gray_array.shape
    if h < 16 or w < 16:
        return 0.0

    # 3x3 Laplacian kernel convolution
    lap = (
        gray_array[:-2, 1:-1].astype(np.float32) +
        gray_array[2:, 1:-1].astype(np.float32) +
        gray_array[1:-1, :-2].astype(np.float32) +
        gray_array[1:-1, 2:].astype(np.float32) -
        4.0 * gray_array[1:-1, 1:-1].astype(np.float32)
    )

    lh, lw = lap.shape
    tile_h = max(2, lh // grid_size)
    tile_w = max(2, lw // grid_size)

    tile_variances: List[float] = []
    for r in range(grid_size):
        r_start = r * tile_h
        r_end = (r + 1) * tile_h if r < grid_size - 1 else lh
        for c in range(grid_size):
            c_start = c * tile_w
            c_end = (c + 1) * tile_w if c < grid_size - 1 else lw
            tile = lap[r_start:r_end, c_start:c_end]
            if tile.size > 4:
                var = float(np.var(tile))
                tile_variances.append(var)

    if not tile_variances:
        return 0.0

    return float(np.percentile(tile_variances, percentile))


def assess_image_quality(
    image_input: Union[bytes, io.BytesIO, Image.Image, np.ndarray, str],
    blur_min: Optional[float] = None,
    dark_max: Optional[float] = None,
    glare_max: Optional[float] = None,
    cover_min: Optional[float] = None,
) -> Dict[str, Any]:
    """Assess document image quality on the page area only.

    Steps:
    1. EXIF rotation correction
    2. Rescale long edge to 640 px (check copy)
    3. Detect form corners & coverage
    4. Measure blur, darkness, glare on warped page area only
    5. Return one clear reason if any check fails

    Returns:
        Dict with keys: ok, reason, issues, blur_score, brightness, glare_pct, coverage, corners
    """
    config = get_quality_config()
    b_min = blur_min if blur_min is not None else config["blur_min"]
    d_max = dark_max if dark_max is not None else config["dark_max"]
    g_max = glare_max if glare_max is not None else config["glare_max"]
    c_min = cover_min if cover_min is not None else config["cover_min"]

    try:
        # Load image
        if isinstance(image_input, (bytes, bytearray)):
            pil_img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, io.BytesIO):
            pil_img = Image.open(image_input)
        elif isinstance(image_input, Image.Image):
            pil_img = image_input
        elif isinstance(image_input, np.ndarray):
            pil_img = Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
        elif isinstance(image_input, str) and os.path.exists(image_input):
            pil_img = Image.open(image_input)
        else:
            return {
                "ok": None,
                "reason": MSG_CHECK_FAILED,
                "issues": [MSG_CHECK_FAILED],
                "blur_score": 0.0,
                "brightness": 0.0,
                "glare_pct": 0.0,
                "coverage": 0.0,
                "corners": None,
            }

        # Step B: Correct EXIF orientation
        try:
            pil_img = ImageOps.exif_transpose(pil_img)
        except Exception:
            pass

        # Step C: Resize long edge to 640 px
        w, h = pil_img.size
        if w <= 0 or h <= 0:
            return {
                "ok": None,
                "reason": MSG_CHECK_FAILED,
                "issues": [MSG_CHECK_FAILED],
                "blur_score": 0.0,
                "brightness": 0.0,
                "glare_pct": 0.0,
                "coverage": 0.0,
                "corners": None,
            }

        scale = 640.0 / max(w, h)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))

        resized_pil = pil_img.convert("RGB").resize((new_w, new_h), Image.Resampling.BILINEAR)
        rgb_check = np.array(resized_pil, dtype=np.uint8)

        # Step D: Detect corners and coverage
        corners, coverage, corner_err = detect_page_corners(rgb_check)

        # Step E: Warp to page area if corners found and not already full-frame
        if corners is not None:
            # Check if corners are already the full image rectangle
            is_full_frame = (
                corners[0][0] <= 2 and corners[0][1] <= 2 and
                corners[1][0] >= new_w - 3 and corners[1][1] <= 2 and
                corners[2][0] >= new_w - 3 and corners[2][1] >= new_h - 3 and
                corners[3][0] <= 2 and corners[3][1] >= new_h - 3
            )
            if is_full_frame:
                page_rgb = rgb_check
            else:
                page_rgb = warp_perspective(rgb_check, corners)
        else:
            page_rgb = rgb_check

        page_gray = cv2.cvtColor(page_rgb, cv2.COLOR_RGB2GRAY)

        # Darkness: Mean brightness of the page (0-255)
        brightness = float(np.mean(page_gray))

        # Glare: Share of near-white and saturated specular pixels (> 250 across RGB channels)
        specular_mask = (
            (page_rgb[:, :, 0] >= 250) &
            (page_rgb[:, :, 1] >= 250) &
            (page_rgb[:, :, 2] >= 250)
        )
        raw_sat_pct = float((np.sum(specular_mask) / page_gray.size) * 100.0)

        # White paper documents should not be treated as glare just because their digital canvas is white.
        # On camera photos of paper, the paper median luminance is typically < 240, while specular glare is >= 250.
        median_lum = float(np.median(page_gray))
        if median_lum >= 245.0:
            glare_pct = 0.0
        else:
            glare_pct = raw_sat_pct

        # Blur: Tile Laplacian variance on the page area (75th percentile of 8x8 tiles)
        blur_score = compute_tile_laplacian_variance(page_gray, grid_size=8, percentile=75.0)

        # Check for pure blank or solid-color image (Laplacian variance near 0)
        total_var = float(np.var(page_gray))
        if total_var < 5.0:
            blur_score = 0.0

        # Step F: Single clear reason by priority
        primary_reason: Optional[str] = None

        if corners is None:
            primary_reason = MSG_CORNERS_NOT_FOUND
        elif coverage < c_min:
            primary_reason = MSG_COVERAGE_LOW
        elif brightness < d_max:
            primary_reason = MSG_TOO_DARK
        elif glare_pct > g_max:
            primary_reason = MSG_GLARE
        elif blur_score < b_min:
            primary_reason = MSG_BLURRY

        is_ok = (primary_reason is None)
        corners_list = corners.tolist() if corners is not None else None

        return {
            "ok": is_ok,
            "reason": primary_reason,
            "issues": [primary_reason] if primary_reason else [],
            "blur_score": round(blur_score, 2),
            "brightness": round(brightness, 2),
            "glare_pct": round(glare_pct, 2),
            "coverage": round(coverage, 1),
            "corners": corners_list,
        }

    except Exception as e:
        logger.warning("Quality assessment error: %s", e)
        return {
            "ok": None,
            "reason": MSG_CHECK_FAILED,
            "issues": [MSG_CHECK_FAILED],
            "blur_score": 0.0,
            "brightness": 0.0,
            "glare_pct": 0.0,
            "coverage": 0.0,
            "corners": None,
        }


def clean_and_enhance_image(
    image_input: Union[bytes, io.BytesIO, Image.Image, np.ndarray, str],
    corners: Optional[Union[np.ndarray, List[List[float]]]] = None,
) -> bytes:
    """Step G: Straighten and enhance document image with OpenCV for Vision AI reading.

    Steps:
    1. Warp the page to a flat, upright rectangle using detected corners.
    2. Convert to greyscale.
    3. Apply CLAHE (clip limit 2.0, tile grid 8x8) to lift faint pen without making page grey.
    4. Resize long edge to 1,568 px.
    5. Encode as JPEG at quality 80, keeping file size strictly under 1 MB.

    Returns:
        Cleaned image JPEG bytes.
    """
    if isinstance(image_input, (bytes, bytearray)):
        pil_img = Image.open(io.BytesIO(image_input))
    elif isinstance(image_input, io.BytesIO):
        pil_img = Image.open(image_input)
    elif isinstance(image_input, Image.Image):
        pil_img = image_input
    elif isinstance(image_input, np.ndarray):
        pil_img = Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
    elif isinstance(image_input, str) and os.path.exists(image_input):
        pil_img = Image.open(image_input)
    else:
        raise ValueError("Invalid image input for cleaning and enhancement")

    try:
        pil_img = ImageOps.exif_transpose(pil_img)
    except Exception:
        pass

    rgb_arr = np.array(pil_img.convert("RGB"), dtype=np.uint8)
    orig_h, orig_w = rgb_arr.shape[:2]

    warped = rgb_arr
    if corners is not None:
        pts = np.array(corners, dtype=np.float32)
        max_c = np.max(pts)
        max_dim = max(orig_h, orig_w)
        if max_c <= 650.0 and max_dim > 650:
            scale_factor = max_dim / 640.0
            pts = pts * scale_factor
        try:
            warped = warp_perspective(rgb_arr, pts)
        except Exception as e:
            logger.warning("Perspective warp failed: %s, continuing with upright unwarped", e)
            warped = rgb_arr
    else:
        scale = 640.0 / max(orig_h, orig_w)
        check_w = max(1, int(round(orig_w * scale)))
        check_h = max(1, int(round(orig_h * scale)))
        check_img = cv2.resize(rgb_arr, (check_w, check_h), interpolation=cv2.INTER_AREA)
        det_corners, cov, _ = detect_page_corners(check_img)
        if det_corners is not None and cov >= 40.0:
            full_corners = det_corners / scale
            try:
                warped = warp_perspective(rgb_arr, full_corners)
            except Exception:
                warped = rgb_arr

    # 2. Convert to greyscale
    if warped.ndim == 3:
        gray = cv2.cvtColor(warped, cv2.COLOR_RGB2GRAY)
    else:
        gray = warped

    # 3. Apply CLAHE (clip limit 2.0, tileGridSize=(8, 8))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 4. Resize long edge to 1,568 px
    eh, ew = enhanced.shape[:2]
    target_dim = 1568
    if max(eh, ew) > 0:
        if ew >= eh:
            new_w = target_dim
            new_h = max(1, int(round(target_dim * eh / ew)))
        else:
            new_h = target_dim
            new_w = max(1, int(round(target_dim * ew / eh)))

        interp = cv2.INTER_AREA if max(eh, ew) > target_dim else cv2.INTER_LINEAR
        enhanced = cv2.resize(enhanced, (new_w, new_h), interpolation=interp)

    # 5. Encode as JPEG at quality 80, ensuring under 1 MB
    quality = 80
    success, encoded = cv2.imencode(".jpg", enhanced, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not success:
        raise RuntimeError("Failed to encode cleaned image as JPEG")

    jpeg_bytes = encoded.tobytes()
    while len(jpeg_bytes) > 1000000 and quality > 40:
        quality -= 10
        _, encoded = cv2.imencode(".jpg", enhanced, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        jpeg_bytes = encoded.tobytes()

    return jpeg_bytes
