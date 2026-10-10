from dataclasses import dataclass


@dataclass
class AgentConfig:
    max_tool_calls: int = 10
    tool_timeout_s: float = 30.0
    model_timeout_s: float = 60.0
    # Most recent image-bearing messages kept with images attached.
    # Matches Groq vision limits (max 3 images per request); older blobs
    # are dropped from the session so they cannot accumulate in memory
    # or get re-sent to the model on every subsequent call.
    max_history_images: int = 3
