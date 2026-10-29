#!/usr/bin/env python3
"""Quality Calibration Tool for Ink 2 Insight (Doc Scanner).

Takes a folder of sharp photos and a folder of blurred photos, computes
sharpness scores using the production tile Laplacian variance metric,
and computes the optimal threshold that catches >= 95% of blurred photos
while minimizing false alarms on sharp photos.

Usage:
    python tools/calibrate_quality.py --sharp-dir path/to/sharp --blur-dir path/to/blur
"""

import os
import sys
import argparse
from typing import List, Tuple

import numpy as np

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.quality_service import assess_image_quality


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


def compute_scores_for_folder(directory: str) -> List[float]:
    """Compute blur scores for all images in a folder."""
    files = collect_image_files(directory)
    scores = []
    for fpath in files:
        try:
            with open(fpath, "rb") as f:
                res = assess_image_quality(f.read())
            if res["ok"] is not None:
                scores.append(res["blur_score"])
        except Exception as e:
            print(f"Skipping {fpath}: {e}", file=sys.stderr)
    return scores


def find_optimal_threshold(
    sharp_scores: List[float], blur_scores: List[float], target_recall: float = 0.95
) -> Tuple[float, float, float]:
    """Find the threshold that catches >= target_recall of blur photos with lowest false alarm on sharp.

    A photo is flagged as blurred if score < threshold.
    Returns:
        (optimal_threshold, blur_recall, sharp_false_alarm_rate)
    """
    if not blur_scores:
        return 80.0, 0.0, 0.0

    # To catch 95% of blur, threshold must be >= the 95th percentile of blur scores
    try:
        threshold = float(np.percentile(blur_scores, target_recall * 100.0, method="higher"))
    except TypeError:
        threshold = float(np.percentile(blur_scores, target_recall * 100.0))
    
    # Calculate actual recall and false alarm
    caught_blur = sum(1 for s in blur_scores if s <= threshold)
    blur_recall = caught_blur / len(blur_scores) if blur_scores else 0.0

    false_alarms = sum(1 for s in sharp_scores if s <= threshold)
    sharp_far = false_alarms / len(sharp_scores) if sharp_scores else 0.0

    return round(threshold, 2), round(blur_recall * 100.0, 1), round(sharp_far * 100.0, 1)


def main():
    parser = argparse.ArgumentParser(description="Calibrate quality threshold for blur detection.")
    parser.add_argument("--sharp-dir", required=True, help="Path to directory containing sharp photos")
    parser.add_argument("--blur-dir", required=True, help="Path to directory containing blurred photos")
    parser.add_argument("--target-recall", type=float, default=0.95, help="Target blur catch rate (default: 0.95)")
    args = parser.parse_args()

    print(f"Scanning sharp photos from: {args.sharp_dir}")
    sharp_scores = compute_scores_for_folder(args.sharp_dir)
    print(f"Loaded {len(sharp_scores)} sharp photo scores.")

    print(f"Scanning blurred photos from: {args.blur_dir}")
    blur_scores = compute_scores_for_folder(args.blur_dir)
    print(f"Loaded {len(blur_scores)} blurred photo scores.")

    if not blur_scores:
        print("Error: No valid blurred photos found.", file=sys.stderr)
        sys.exit(1)

    threshold, recall, far = find_optimal_threshold(sharp_scores, blur_scores, args.target_recall)

    print("\n" + "=" * 50)
    print("CALIBRATION RESULTS:")
    print(f"  Target Recall:       {args.target_recall * 100.0:.1f}%")
    print(f"  Optimal Threshold:   QUALITY_BLUR_MIN={threshold}")
    print(f"  Blur Catch Rate:     {recall}%")
    print(f"  Sharp False Alarms:  {far}%")
    print("=" * 50)
    print(f"\nRecommended env configuration:\nQUALITY_BLUR_MIN={threshold}")


if __name__ == "__main__":
    main()
