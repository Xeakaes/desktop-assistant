#!/usr/bin/env python3
"""Interactive CLI for the desktop assistant core (temporary M0 front-end)."""

from __future__ import annotations

import signal
import sys

from core.bootstrap import build_runtime


def main() -> int:
    try:
        runtime, events, session = build_runtime()
    except Exception as exc:
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        return 1

    def on_event(e):
        if e.name in ("agent_started", "agent_finished", "agent_error", "agent_cancelled"):
            print(f"[{e.name}] {e.payload}")
        elif e.name == "assistant_message":
            print(f"[assistant] {e.payload.get('text', '')}")
        elif e.name == "tool_started":
            print(f"[tool_started] {e.payload.get('tool_name')} {e.payload.get('arguments')}")
        elif e.name == "tool_finished":
            print(f"[tool_finished] {e.payload.get('tool_name')} ok={e.payload.get('ok')}")
        elif e.name == "confirmation_requested":
            answer = input(
                f"[onay] {e.payload.get('question', 'Run tool?')} [e/h]: "
            ).strip().lower()
            approved = answer in ("e", "evet", "y", "yes")
            runtime.resolve_confirmation(e.task_id, e.payload["confirm_id"], approved)

    events.subscribe("*", on_event)
    session_id = session.create_session()
    print("M0 CLI — mesaj yazın, çıkmak için Ctrl+D veya 'çık'.")

    previous_handler = signal.getsignal(signal.SIGINT)

    def on_sigint(signum, frame):
        runtime.cancel_active_task()

    while True:
        try:
            signal.signal(signal.SIGINT, on_sigint)
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        finally:
            signal.signal(signal.SIGINT, previous_handler)
        if not line:
            continue
        if line.lower() in ("çık", "cik", "exit", "quit"):
            break
        task_id = runtime.begin_task(session_id, line)
        signal.signal(signal.SIGINT, on_sigint)
        try:
            runtime.run_task(task_id)
        finally:
            signal.signal(signal.SIGINT, previous_handler)
    runtime.cancel_active_task()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
