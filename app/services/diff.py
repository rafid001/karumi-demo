import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim


def visual_diff_score(old_path: str, new_path: str) -> float:
    """Return dissimilarity score: 0.0 = identical, 1.0 = completely different."""
    old_img = np.array(Image.open(old_path).convert("RGB"))
    new_img = np.array(Image.open(new_path).convert("RGB"))

    if old_img.shape != new_img.shape:
        new_img_pil = Image.open(new_path).convert("RGB").resize(
            (old_img.shape[1], old_img.shape[0]), Image.Resampling.LANCZOS
        )
        new_img = np.array(new_img_pil)

    score, _ = ssim(old_img, new_img, channel_axis=2, full=True)
    return float(1.0 - score)
