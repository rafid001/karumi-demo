from app.core.healer import drift_log_needs_healing, parse_semantic_diff


class FakeDriftLog:
    def __init__(self, healed=False, semantic_diff=None):
        self.healed = healed
        self.semantic_diff = semantic_diff


def test_needs_healing_from_flag():
    log = FakeDriftLog(
        healed=False,
        semantic_diff='{"needs_healing": true, "change_type": "functional"}',
    )
    assert drift_log_needs_healing(log) is True


def test_needs_healing_already_healed():
    log = FakeDriftLog(
        healed=True,
        semantic_diff='{"needs_healing": true}',
    )
    assert drift_log_needs_healing(log) is False


def test_needs_healing_cosmetic():
    log = FakeDriftLog(
        healed=False,
        semantic_diff='{"needs_healing": false, "change_type": "cosmetic"}',
    )
    assert drift_log_needs_healing(log) is False


def test_parse_semantic_diff_invalid():
    assert parse_semantic_diff("not json") == {}
