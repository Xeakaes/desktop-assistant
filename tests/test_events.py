from core.events import EventBus, Event

def test_publish_delivers_with_ids():
    bus = EventBus(); seen = []
    bus.subscribe("agent_started", seen.append)
    bus.publish("agent_started", "s1", "t1", {"user_text": "hi"})
    assert seen == [Event("agent_started", "s1", "t1", {"user_text": "hi"})]

def test_wildcard_receives_all():
    bus = EventBus(); names = []
    bus.subscribe("*", lambda e: names.append(e.name))
    bus.publish("a", "s", "t", {}); bus.publish("b", "s", "t", {})
    assert names == ["a", "b"]

def test_unsubscribe_stops_delivery():
    bus = EventBus(); seen = []
    cb = seen.append
    bus.subscribe("x", cb); bus.unsubscribe("x", cb)
    bus.publish("x", "s", "t", {})
    assert seen == []

def test_event_name_list_matches_spec():
    from core.events import EVENT_NAMES
    assert set(EVENT_NAMES) >= {
        "agent_started", "assistant_message", "tool_started", "tool_finished",
        "confirmation_requested", "agent_error", "agent_finished", "agent_cancelled"}
