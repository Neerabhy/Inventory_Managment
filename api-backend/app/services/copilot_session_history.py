from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


HISTORY_PATH = Path("generated-reports/copilot_session_history.json")


def reset_copilot_history() -> None:
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(
            json.dumps(
                {
                    "reset_at": datetime.now(timezone.utc).isoformat(),
                    "turns": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except PermissionError:
        return


def append_copilot_turn(query: str, answer: str, context: Dict[str, Any] | None = None) -> None:
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if HISTORY_PATH.exists():
            try:
                payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {"reset_at": None, "turns": []}
        else:
            payload = {"reset_at": None, "turns": []}

        turns: List[Dict[str, Any]] = payload.setdefault("turns", [])
        turns.append(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "query": query,
                "answer": answer,
                "context": context or {},
            }
        )
        HISTORY_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except PermissionError:
        return
