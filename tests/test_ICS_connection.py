"""
Smoke-test ICS addTask.

    uv run python scripts/test_ics_add_task.py
    uv run python scripts/test_ics_add_task.py --dry-run
    uv run python scripts/test_ics_add_task.py --url http://192.168.50.250:7000/ics/taskOrder/addTask
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from config.settings import settings

DEFAULT_URL = "http://192.168.50.250:7000/ics/taskOrder/addTask"
DEFAULT_PATH = "10000066,10000105"  # A2 → Line1


def build_payload(task_path: str) -> dict:
    return {
        "modelProcessCode": "FL",
        "fromSystem": "ICS",
        "orderId": str(time.time()),
        "taskOrderDetail": [{"taskPath": task_path}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Test ICS addTask")
    parser.add_argument("--url", default=settings.ICS_URL or DEFAULT_URL)
    parser.add_argument("--path", default=DEFAULT_PATH, help="taskPath start,end")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    payload = build_payload(args.path)
    print(f"POST {args.url}")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("\n(dry-run — chưa gọi API)")
        return 0

    try:
        resp = requests.post(args.url, json=payload, timeout=args.timeout)
    except requests.RequestException as e:
        print(f"\n❌ request failed: {e}")
        return 1

    print(f"\nHTTP {resp.status_code}")
    try:
        body = resp.json()
        print(json.dumps(body, indent=2, ensure_ascii=False))
    except ValueError:
        print(resp.text)
        return 1

    ok = resp.status_code == 200 and body.get("code") == 1000
    print("\n✅ ICS accepted" if ok else "\n❌ ICS rejected / unexpected")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())