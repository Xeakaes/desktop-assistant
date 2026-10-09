from ui.settings import KNOWN_TOOLS, merge_permissions


def test_merge_preserves_unknown_tool_entries():
    existing = {"*": "ask", "mouse": "deny", "ocr_screen": "deny", "screenshot": "allow"}
    per_tool = {"screenshot": "ask", "ocr_screen": "ask", "list_windows": "ask"}
    merged = merge_permissions(existing, "ask", per_tool)
    assert merged["mouse"] == "deny"          # not shown in UI — kept
    assert merged["screenshot"] == "ask"      # UI updated
    assert merged["ocr_screen"] == "ask"
    assert merged["list_windows"] == "ask"
    assert merged["*"] == "ask"


def test_known_tools_match_registry_names():
    assert set(KNOWN_TOOLS) == {
        "screenshot", "ocr_screen", "mouse", "keyboard", "list_windows", "focus_window",
    }
