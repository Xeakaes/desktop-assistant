from dataclasses import dataclass


@dataclass
class AgentConfig:
    max_tool_calls: int = 10
    tool_timeout_s: float = 30.0
    model_timeout_s: float = 60.0
