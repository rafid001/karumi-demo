def test_normalize_steps_maps_node_ids():
    from app.core.narrator import DemoNarrator

    narrator = DemoNarrator(db=None)  # type: ignore[arg-type]
    nodes = [
        {"id": "a1", "url": "https://example.com", "title": "Home", "elements": []},
        {"id": "b2", "url": "https://example.com/about", "title": "About", "elements": []},
    ]
    raw = [
        {"node_id": "a1", "action": "Browse home", "narration": "Welcome"},
        {"node_id": "invalid", "action": "Go about", "narration": "About page"},
    ]
    result = narrator._normalize_steps(raw, {"a1": nodes[0]}, nodes)
    assert len(result) == 2
    assert result[0]["node_id"] == "a1"
    assert result[1]["url"] == "https://example.com/about"
