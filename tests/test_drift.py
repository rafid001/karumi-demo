from app.core.drift_detector import DriftDetector


def test_is_meaningful_cosmetic():
    detector = DriftDetector(db=None)  # type: ignore[arg-type]
    assert detector._is_meaningful({"change_type": "cosmetic", "severity": "low"}) is False


def test_is_meaningful_functional():
    detector = DriftDetector(db=None)  # type: ignore[arg-type]
    assert detector._is_meaningful({"change_type": "functional", "severity": "high"}) is True


def test_is_meaningful_unknown():
    detector = DriftDetector(db=None)  # type: ignore[arg-type]
    assert detector._is_meaningful({"change_type": "unknown", "severity": "medium"}) is True
