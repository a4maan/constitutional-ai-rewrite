from core.memory import ResidentMemoryBuffer


def test_memory_buffer_formats_turn_summary() -> None:
    buffer = ResidentMemoryBuffer(capacity=3)
    observation = {
        "position": [2, 3],
        "hunger_state": {"energy": 85, "status": "Energetic"},
        "notifications": [
            "Heard movement nearby",
            "Saw Orin near the market",
        ],
    }
    payloads = [
        {"action": "MOVE", "parameters": {"direction": "N"}},
        {"action": "GATHER", "parameters": {"resource": "wood"}},
        {"action": "COMMUNICATE", "parameters": {"message": "Heading north for supplies"}},
    ]

    snapshot = buffer.record(
        turn=5,
        observation=observation,
        reasoning="Need to regroup with the alliance before venturing deeper.",
        payloads=payloads,
    )

    assert len(snapshot) == 1
    entry = snapshot[0]
    assert "Turn 5 @ (2, 3)" in entry
    assert "Energy 85 (Energetic)" in entry
    assert "Thought: Need to regroup with the alliance before venturing deeper." in entry
    assert 'Actions: moved N; gathered wood; broadcasted "Heading north for supplies"' in entry
    assert "Alerts:" in entry


def test_memory_buffer_load_sanitizes_and_limits_capacity() -> None:
    buffer = ResidentMemoryBuffer(capacity=2)
    snapshot = buffer.load(
        [
            "  First entry  ",
            "Second   line\n",
            "",
            "Third entry appears",
        ]
    )

    assert snapshot == ["Second line", "Third entry appears"]

