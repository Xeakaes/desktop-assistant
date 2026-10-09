from dataclasses import fields
from core.tools.base import ToolResult, Tool
from core.agent.cancellation import CancellationToken

def test_toolresult_field_names():
    assert [f.name for f in fields(ToolResult)] == ["ok", "data", "error", "error_code"]

def test_tool_is_abstract_shape():
    class T(Tool):
        name = "t"; description = "d"; input_schema = {"type": "object"}
        def execute(self, arguments, cancel):
            return ToolResult(ok=True, data={"echo": arguments})
    r = T().execute({"a": 1}, CancellationToken())
    assert r.ok and r.data == {"echo": {"a": 1}} and r.error is None and r.error_code is None
