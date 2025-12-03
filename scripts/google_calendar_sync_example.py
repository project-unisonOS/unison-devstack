"""
Example skeleton for syncing Google Calendar events into UnisonOS.

IMPORTANT:
- This file is intentionally generic and does NOT contain any Google-specific
  code, credentials, or personal data.
- To use it with your real calendar:
  - Copy it into a local, gitignored path (for example `local/google_calendar_sync.py`).
  - Add your Google API calls in `fetch_calendar_events`.
  - Configure env vars and OAuth tokens locally.

This example shows:
- How to talk to Unison orchestrator and context.
- How to map events into workflows and dashboard cards.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


PERSON_ID = os.environ.get("UNISON_PERSON_ID", "local-user")
ORCH_URL = os.environ.get("UNISON_ORCH_URL", "http://localhost:8080")
CONTEXT_URL = os.environ.get("UNISON_CONTEXT_URL", "http://localhost:8081")


def enroll_person() -> None:
    """Ensure a basic profile exists for the local person."""
    profile = {
        "name": "Local User",
        "locale": "en-US",
        "dashboard": {
            "preferences": {
                "layout": "briefing-first",
                "density": "comfortable",
            }
        },
    }
    resp = requests.post(f"{CONTEXT_URL}/profile/{PERSON_ID}", json={"profile": profile}, timeout=5)
    resp.raise_for_status()


def fetch_calendar_events() -> List[Dict[str, Any]]:
    """
    Placeholder for fetching Google Calendar events.

    Replace this stub with real Google Calendar API calls in your local copy.
    Returned events SHOULD NOT be committed to source control.

    Expected shape (simplified):
    [
        {
            "id": "provider_event_id",
            "summary": "Design review with Alex",
            "start": {"dateTime": "..."},
            "end": {"dateTime": "..."},
            "location": "Video",
        },
        ...
    ]
    """
    # Example synthetic event for demonstration purposes only.
    return [
        {
            "id": "example-1",
            "summary": "Synthetic design review",
            "start": {"dateTime": "2026-04-10T09:00:00"},
            "end": {"dateTime": "2026-04-10T10:00:00"},
            "location": "Video",
        }
    ]


def build_day_plan_workflow(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Construct a workflow.design payload for a simple day plan from events."""
    workflow_id = "day-plan-example"
    changes: List[Dict[str, Any]] = []
    for idx, ev in enumerate(events):
        summary = ev.get("summary") or "Event"
        start = ev.get("start", {}).get("dateTime") or ""
        title = f"{start[-8:-3]} – {summary}" if start else summary
        changes.append(
            {
                "op": "add_step",
                "title": title,
                "position": idx,
            }
        )
    payload = {
        "person_id": PERSON_ID,
        "workflow_id": workflow_id,
        "project_id": "calendar-day-plan",
        "mode": "design",
        "changes": changes,
    }
    return payload


def invoke_workflow_design(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call the orchestrator workflow.design skill."""
    body = {"intent": "workflow.design", "payload": payload}
    resp = requests.post(f"{ORCH_URL}/skills/invoke", json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    enroll_person()
    events = fetch_calendar_events()
    if not events:
        print("No events to sync.")
        return
    payload = build_day_plan_workflow(events)
    result = invoke_workflow_design(payload)
    print("workflow.design result:", result)


if __name__ == "__main__":
    main()

