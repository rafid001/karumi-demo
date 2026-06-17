import uuid
from pathlib import Path

from app.config import settings


class ScreenshotService:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.screenshot_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path_for_node(self, product_id: uuid.UUID, node_id: uuid.UUID) -> Path:
        product_dir = self.base_dir / str(product_id)
        product_dir.mkdir(parents=True, exist_ok=True)
        return product_dir / f"{node_id}.png"

    def save_bytes(self, product_id: uuid.UUID, node_id: uuid.UUID, data: bytes) -> str:
        path = self.path_for_node(product_id, node_id)
        path.write_bytes(data)
        return str(path)

    def path_for_drift(self, product_id: uuid.UUID, node_id: uuid.UUID) -> Path:
        drift_dir = self.base_dir / str(product_id) / "drift"
        drift_dir.mkdir(parents=True, exist_ok=True)
        return drift_dir / f"{node_id}.png"

    def save_drift_bytes(self, product_id: uuid.UUID, node_id: uuid.UUID, data: bytes) -> str:
        path = self.path_for_drift(product_id, node_id)
        path.write_bytes(data)
        return str(path)

    def exists(self, screenshot_path: str) -> bool:
        return Path(screenshot_path).exists()
