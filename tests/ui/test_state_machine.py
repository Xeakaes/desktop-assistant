from ui.avatar.state_machine import reduce_event


def test_each_event_maps_to_expected_state():
    cases = [
        ("idle", "agent_started", "thinking"),
        ("thinking", "tool_started", "working"),
        ("working", "tool_finished", "working"),
        ("working", "confirmation_requested", "working"),
        ("working", "assistant_message", "speaking"),
        ("speaking", "agent_finished", "idle"),
        ("working", "agent_cancelled", "idle"),
        ("idle", "agent_error", "error"),
        ("error", "error_timeout", "idle"),
    ]
    for cur, ev, want in cases:
        assert reduce_event(cur, ev) == want, (cur, ev)


def test_unknown_event_returns_current_state():
    assert reduce_event("thinking", "weird_new_event") == "thinking"
    assert reduce_event("error", "some_future_event") == "error"
