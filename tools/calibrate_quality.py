#!/usr/bin/env python3
"""Quality Calibration Tool for Ink 2 Insight (Doc Scanner).

Calibrates quality thresholds for medical camp intake form photos:
1. Blur threshold (QUALITY_BLUR_MIN) on sharp vs blurred photos, computing:
   - Optimal blur threshold
   - Blur catch rate (Recall)
   - Miss rate (100% - Recall)
   - False alarm rate on sharp photos (FAR)
2. Darkness threshold (QUALITY_DARK_MAX) on normal vs dark photos
3. Glare threshold (QUALITY_GLARE_MAX) on normal vs glare photos
4. Coverage threshold (QUALITY_COVER_MIN)

Usage:
    python tools/calibrate_quality.py --sharp-dir path/to/sharp --blur-dir path/to/blur
"""

import os
import sys
import argparse
import json
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.services.quality_service import assess_image_quality
except ImportError:
    from services.quality_service import assess_image_quality


def collect_image_files(directory: str) -> List[str]:
    """Scan folder for valid image files."""
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    files = []
    if not os.path.exists(directory):
        return []
    for root, _, filenames in os.walk(directory):
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_exts:
                files.append(os.path.join(root, f))
    return sorted(files)


def compute_metrics_for_folder(directory: str) -> Dict[str, List[float]]:
    """Compute blur scores, brightness, and glare for all images in a folder."""
    files = collect_image_files(directory)
    metrics: Dict[str, List[float]] = {
        "blur_scores": [],
        "brightness": [],
        "glare_pct": [],
        "coverage": [],
    }
    for fpath in files:
        try:
            with open(fpath, "rb") as f:
                res = assess_image_quality(f.read())
            if res.get("ok") is not None:
                metrics["blur_scores"].append(float(res.get("blur_score", 0.0)))
                metrics["brightness"].append(float(res.get("brightness", 0.0)))
                metrics["glare_pct"].append(float(res.get("glare_pct", 0.0)))
                metrics["coverage"].append(float(res.get("coverage", 0.0)))
        except Exception as e:
            print(f"Skipping {fpath}: {e}", file=sys.stderr)
    return metrics


def find_optimal_blur_threshold(
    sharp_scores: List[float],
    blur_scores: List[float],
    target_recall: float = 0.95
) -> Dict[str, Any]:
    """Find the threshold that catches >= target_recall of blur photos with lowest false alarm on sharp.

    A photo is flagged as blurred if score < threshold.
    Returns:
        Dict with keys: optimal_threshold, blur_recall, miss_rate, sharp_false_alarm_rate
    """
    if not blur_scores:
        return {
            "optimal_threshold": 40.0,
            "blur_recall": 0.0,
            "miss_rate": 100.0,
            "sharp_false_alarm_rate": 0.0,
        }

    # To catch >= target_recall of blur, threshold must be >= target_recall percentile of blur scores
    try:
        threshold = float(np.percentile(blur_scores, target_recall * 100.0, method="higher"))
    except TypeError:
        threshold = float(np.percentile(blur_scores, target_recall * 100.0))

    threshold = max(10.0, round(threshold, 2))

    caught_blur = sum(1 for s in blur_scores if s <= threshold)
    blur_recall = (caught_blur / len(blur_scores)) * 100.0 if blur_scores else 0.0
    miss_rate = 100.0 - blur_recall

    false_alarms = sum(1 for s in sharp_scores if s <= threshold)
    sharp_far = (false_alarms / len(sharp_scores)) * 100.0 if sharp_scores else 0.0

    return {
        "optimal_threshold": threshold,
        "blur_recall": round(blur_recall, 1),
        "miss_rate": round(miss_rate, 1),
        "sharp_false_alarm_rate": round(sharp_far, 1),
        "target_recall": round(target_recall * 100.0, 1),
    }


def generate_calibration_report(
    sharp_metrics: Dict[str, List[float]],
    blur_metrics: Dict[str, List[float]],
    dark_metrics: Optional[Dict[str, List[float]]] = None,
    glare_metrics: Optional[Dict[str, List[float]]] = None,
    target_recall: float = 0.95,
) -> Dict[str, Any]:
    """Generate comprehensive calibration analysis and report."""
    blur_cal = find_optimal_blur_threshold(
        sharp_metrics.get("blur_scores", []),
        blur_metrics.get("blur_scores", []),
        target_recall=target_recall
    )

    # Darkness threshold calibration:
    # If dark photos provided, find max brightness among dark photos
    dark_max = 75.0
    if dark_metrics and dark_metrics.get("brightness"):
        dark_scores = dark_metrics["brightness"]
        dark_max = round(float(np.percentile(dark_scores, 95.0)), 1)

    # Glare threshold calibration:
    glare_max = 12.0
    if glare_metrics and glare_metrics.get("glare_pct"):
        # Glare photos typically have glare_pct > 10%
        glare_scores = glare_metrics["glare_pct"]
        glare_max = round(float(np.percentile(glare_scores, 10.0)), 1)

    cover_min = 60.0

    report = {
        "calibration": {
            "QUALITY_BLUR_MIN": blur_cal["optimal_threshold"],
            "QUALITY_DARK_MAX": dark_max,
            "QUALITY_GLARE_MAX": glare_max,
            "QUALITY_COVER_MIN": cover_min,
        },
        "performance": {
            "blur_catch_rate": blur_cal["blur_recall"],
            "miss_rate": blur_cal["miss_rate"],
            "sharp_false_alarm_rate": blur_cal["sharp_false_alarm_rate"],
            "target_recall": blur_cal["target_recall"],
        },
        "sample_counts": {
            "sharp_samples": len(sharp_metrics.get("blur_scores", [])),
            "blur_samples": len(blur_metrics.get("blur_scores", [])),
            "dark_samples": len(dark_metrics.get("brightness", [])) if dark_metrics else 0,
            "glare_samples": len(glare_metrics.get("glare_pct", [])) if glare_metrics else 0,
        }
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Calibrate quality thresholds for medical camp intake forms.")
    parser.add_argument("--sharp-dir", required=True, help="Directory containing sharp camp form photos")
    parser.add_argument("--blur-dir", required=True, help="Directory containing blurred camp form photos")
    parser.add_argument("--dark-dir", default=None, help="Optional directory containing dark camp form photos")
    parser.add_argument("--glare-dir", default=None, help="Optional directory containing glare camp form photos")
    parser.add_argument("--target-recall", type=float, default=0.95, help="Target blur recall (default: 0.95)")
    parser.add_argument("--report-out", default=None, help="Path to write JSON calibration report")
    args = parser.parse_args()

    print(f"Scanning sharp photos from: {args.sharp_dir}")
    sharp_metrics = compute_metrics_for_folder(args.sharp_dir)
    print(f"Loaded {len(sharp_metrics['blur_scores'])} sharp photo scores.")

    print(f"Scanning blurred photos from: {args.blur_dir}")
    blur_metrics = compute_metrics_for_folder(args.blur_dir)
    print(f"Loaded {len(blur_metrics['blur_scores'])} blurred photo scores.")

    if not blur_metrics["blur_scores"]:
        print("Error: No valid blurred photos found.", file=sys.stderr)
        sys.exit(1)

    dark_metrics = compute_metrics_for_folder(args.dark_dir) if args.dark_dir else None
    glare_metrics = compute_metrics_for_folder(args.glare_dir) if args.glare_dir else None

    report = generate_calibration_report(
        sharp_metrics,
        blur_metrics,
        dark_metrics=dark_metrics,
        glare_metrics=glare_metrics,
        target_recall=args.target_recall,
    )

    cal = report["calibration"]
    perf = report["performance"]
    counts = report["sample_counts"]

    print("\n" + "=" * 60)
    print("INK 2 INSIGHT DOC SCANNER CALIBRATION REPORT")
    print("=" * 60)
    print(f"  Target Recall:            {perf['target_recall']}%")
    print(f"  Blur Threshold:           QUALITY_BLUR_MIN={cal['QUALITY_BLUR_MIN']}")
    print(f"  Blur Catch Rate (Recall): {perf['blur_catch_rate']}%")
    print(f"  Miss Rate:                {perf['miss_rate']}%")
    print(f"  False Alarm Rate (FAR):   {perf['sharp_false_alarm_rate']}%")
    print("-" * 60)
    print(f"  Dark Threshold:           QUALITY_DARK_MAX={cal['QUALITY_DARK_MAX']}")
    print(f"  Glare Threshold:          QUALITY_GLARE_MAX={cal['QUALITY_GLARE_MAX']}")
    print(f"  Coverage Threshold:       QUALITY_COVER_MIN={cal['QUALITY_COVER_MIN']}")
    print("=" * 60)
    print(f"\nRecommended Environment Configuration:")
    print(f"QUALITY_BLUR_MIN={cal['QUALITY_BLUR_MIN']}")
    print(f"QUALITY_DARK_MAX={cal['QUALITY_DARK_MAX']}")
    print(f"QUALITY_GLARE_MAX={cal['QUALITY_GLARE_MAX']}")
    print(f"QUALITY_COVER_MIN={cal['QUALITY_COVER_MIN']}")
    print("=" * 60)

    if args.report_out:
        with open(args.report_out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Saved calibration report to: {args.report_out}")


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# Backward-compatibility alias (test_v1_task2.py imports the old tuple-returning name)
# ---------------------------------------------------------------------------
def find_optimal_threshold(
    sharp_scores: List[float], blur_scores: List[float], target_recall: float = 0.95
) -> Tuple[float, float, float]:
    """Find the threshold that catches >= target_recall of blur photos.

    Returns:
        (optimal_threshold, blur_recall, sharp_false_alarm_rate)
    """
    cal = find_optimal_blur_threshold(sharp_scores, blur_scores, target_recall)
    return cal["optimal_threshold"], cal["blur_recall"], cal["sharp_false_alarm_rate"]
