#!/usr/bin/env python3
"""
Multimodal probe that emits a capability manifest JSON.
Tries to detect real hardware via lightweight system calls; falls back to stubs.
"""

import json
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _run(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)
        return res.stdout.strip()
    except Exception:
        return ""


def detect_displays() -> List[Dict[str, Any]]:
    # Try xrandr if available
    out = _run(["sh", "-c", "which xrandr >/dev/null 2>&1 && xrandr --query"])
    displays = []
    for line in out.splitlines():
        if " connected" in line:
            parts = line.split()
            name = parts[0]
            res = next((p for p in parts if "x" in p and "+" in p), None)
            displays.append({"id": name, "name": name, "primary": "primary" in line, "resolution": res or "unknown"})
    return displays


def detect_audio_devices(kind: str) -> List[Dict[str, Any]]:
    # kind in {"sinks", "sources"}
    out = _run(["sh", "-c", f"which pactl >/dev/null 2>&1 && pactl list short {kind}"])
    devices = []
    for line in out.splitlines():
        cols = line.split("\t")
        if len(cols) >= 2:
            devices.append({"id": cols[0], "name": cols[1]})
    return devices


def detect_cameras() -> List[Dict[str, Any]]:
    out = _run(["sh", "-c", "ls /dev/video* 2>/dev/null"])
    return [{"id": dev, "name": dev} for dev in out.split()] if out else []


def build_manifest() -> dict:
    hostname = socket.gethostname()
    displays = detect_displays() or [{"id": "display-1", "name": f"{hostname}-display", "primary": True, "resolution": "1920x1080"}]
    speakers = detect_audio_devices("sinks") or [{"id": "speaker-1", "name": f"{hostname}-speaker"}]
    microphones = detect_audio_devices("sources") or [{"id": "mic-1", "name": f"{hostname}-mic"}]
    cameras = detect_cameras()
    return {
        "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deployment_mode": "host",
        "modalities": {
            "displays": displays,
            "speakers": speakers,
            "microphones": microphones,
            "cameras": cameras,
        },
    }


def main() -> None:
    manifest = build_manifest()
    out = Path("capabilities.json")
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {out} with {len(manifest['modalities'].get('displays', []))} display(s)")


if __name__ == "__main__":
    main()
