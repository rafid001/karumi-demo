import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "pixelmatch_diff.js"


def _ssim_diff_score(old_path: str, new_path: str) -> float:
    """Fallback dissimilarity score using SSIM when pixelmatch is unavailable."""
    old_img = np.array(Image.open(old_path).convert("RGB"))
    new_img = np.array(Image.open(new_path).convert("RGB"))

    if old_img.shape != new_img.shape:
        new_img_pil = Image.open(new_path).convert("RGB").resize(
            (old_img.shape[1], old_img.shape[0]), Image.Resampling.LANCZOS
        )
        new_img = np.array(new_img_pil)

    score, _ = ssim(old_img, new_img, channel_axis=2, full=True)
    return float(1.0 - score)


def visual_diff_score(old_path: str, new_path: str) -> tuple[float, str]:
    """Return (dissimilarity score, method). 0.0 = identical, 1.0 = completely different."""
    if not SCRIPT_PATH.exists():
        return _ssim_diff_score(old_path, new_path), "ssim"

    try:
        result = subprocess.run(
            ["node", str(SCRIPT_PATH), old_path, new_path],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        payload = json.loads(result.stdout.strip())
        return float(payload["score"]), payload.get("method", "pixelmatch")
    except Exception:
        return _ssim_diff_score(old_path, new_path), "ssim"
