"""
validator.py — Phase 0.4–0.8: Pre-submit CSV validator.
Checks headers, row count, ID order, enums, numeric bounds, payment plan format,
spending change format, and key invariants.
"""

from __future__ import annotations
import csv
import re
import sys
from pathlib import Path
from typing import List, Optional

from schema import (
    OUTPUT_COLUMNS,
    AFFORDABILITY_STATUSES,
    PAYMENT_METHODS,
    DATE_RE,
    PAYMENT_PLAN_ENTRY_RE,
    SPENDING_CHANGE_RE,
)

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
RESET = "\033[0m"

_errors: List[str] = []
_warnings: List[str] = []


def _err(msg: str) -> None:
    _errors.append(msg)


def _warn(msg: str) -> None:
    _warnings.append(msg)


def validate_output_csv(
    output_path: Path,
    requests_path: Path,
    dataset_path: Optional[Path] = None,
) -> bool:
    """
    Full pre-submit validator. Returns True if GREEN, False if any errors.
    """
    global _errors, _warnings
    _errors = []
    _warnings = []

    # ── Read requests (expected IDs in order) ──────────────────────────────
    if not requests_path.exists():
        _err(f"requests.csv not found at {requests_path}")
        _print_result()
        return False

    with open(requests_path, newline="", encoding="utf-8") as f:
        req_reader = list(csv.DictReader(f))

    expected_ids   = [r["request_id"] for r in req_reader]
    req_lookup     = {r["request_id"]: r for r in req_reader}

    # ── Read output ────────────────────────────────────────────────────────
    if not output_path.exists():
        _err(f"output.csv not found at {output_path}")
        _print_result()
        return False

    with open(output_path, newline="", encoding="utf-8") as f:
        raw = f.read()

    # Re-read in fresh reader (Phase 0.4 requirement)
    rows = list(csv.DictReader(raw.splitlines()))

    # ── 0.1 Header check ──────────────────────────────────────────────────
    if not rows:
        _err("output.csv is empty (no rows, not even header)")
        _print_result()
        return False

    actual_cols = list(csv.DictReader(raw.splitlines()).fieldnames or [])
    if actual_cols != OUTPUT_COLUMNS:
        _err(
            f"Header mismatch.\n"
            f"  Expected: {OUTPUT_COLUMNS}\n"
            f"  Got:      {actual_cols}"
        )

    # ── 0.2 Row count ─────────────────────────────────────────────────────
    if len(rows) != len(expected_ids):
        _err(
            f"Row count mismatch: expected {len(expected_ids)}, got {len(rows)}"
        )

    # ── 0.2 Row order ─────────────────────────────────────────────────────
    actual_ids = [r.get("request_id", "") for r in rows]
    if actual_ids != expected_ids:
        mismatches = [
            (i, e, a)
            for i, (e, a) in enumerate(zip(expected_ids, actual_ids))
            if e != a
        ]
        _err(
            f"Row order mismatch. First 5 mismatches: {mismatches[:5]}"
        )

    # ── Per-row checks ─────────────────────────────────────────────────────
    for i, row in enumerate(rows):
        rid = row.get("request_id", f"<row {i}>")
        req = req_lookup.get(rid, {})

        _check_row(i, rid, row, req)

    _print_result()
    return len(_errors) == 0


def _check_row(i: int, rid: str, row: dict, req: dict) -> None:
    """Per-row field checks."""

    # ── 0.3 No-empty-cell enforcement (except earliest_date_for_full_payment) ──
    required_non_empty = [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "spending_changes_needed",
        "decision_explanation",
    ]
    for col in required_non_empty:
        if not row.get(col, "").strip():
            _err(f"[{rid}] Empty required field: {col}")

    # ── 0.5 Enum checks ───────────────────────────────────────────────────
    status = row.get("affordability_status", "")
    if status and status not in AFFORDABILITY_STATUSES:
        _err(f"[{rid}] Invalid affordability_status: '{status}'")

    method = row.get("recommended_payment_method", "")
    if method and method not in PAYMENT_METHODS:
        _err(f"[{rid}] Invalid recommended_payment_method: '{method}'")

    # ── 0.8 Numeric bounds ────────────────────────────────────────────────
    raw_amount = row.get("amount_safe_to_pay", "")
    try:
        amount_safe = float(raw_amount)
    except (ValueError, TypeError):
        _err(f"[{rid}] amount_safe_to_pay is not numeric: '{raw_amount}'")
        amount_safe = None

    requested = None
    if req.get("requested_amount"):
        try:
            requested = float(req["requested_amount"])
        except ValueError:
            pass

    if amount_safe is not None:
        if amount_safe < 0:
            _err(f"[{rid}] amount_safe_to_pay < 0: {amount_safe}")
        if requested is not None and amount_safe > requested + 0.01:
            _err(
                f"[{rid}] amount_safe_to_pay ({amount_safe}) > requested_amount ({requested})"
            )

    # ── 0.8 Invariant: affordable_now ⇒ earliest_date == request_date ────
    earliest = row.get("earliest_date_for_full_payment", "")
    request_date = req.get("request_date", "")
    if status == "affordable_now":
        if earliest and earliest != request_date:
            _err(
                f"[{rid}] affordable_now but earliest_date_for_full_payment "
                f"'{earliest}' != request_date '{request_date}'"
            )
        if not earliest:
            _warn(f"[{rid}] affordable_now but earliest_date_for_full_payment is blank")

    # ── 0.8 Invariant: not_affordable / not_recommended ⇒ earliest blank ─
    if status == "not_affordable" and earliest:
        _warn(f"[{rid}] not_affordable but earliest_date is set: '{earliest}'")

    # ── 0.6 Payment plan format ───────────────────────────────────────────
    plan = row.get("payment_plan", "")
    if plan and plan != "none":
        plan_entries = plan.split("|")
        for entry in plan_entries:
            if not PAYMENT_PLAN_ENTRY_RE.match(entry.strip()):
                _err(
                    f"[{rid}] Invalid payment_plan entry: '{entry}'. "
                    "Must be YYYY-MM-DD:amount"
                )
        # ── 0.8 partial_payment ⇒ exactly 2 payments summing to requested ──
        if method == "partial_payment":
            if len(plan_entries) != 2:
                _err(
                    f"[{rid}] partial_payment must have exactly 2 payment entries, "
                    f"got {len(plan_entries)}"
                )
            elif requested is not None and amount_safe is not None:
                try:
                    amounts = [float(e.split(":")[1]) for e in plan_entries]
                    total = sum(amounts)
                    if abs(total - requested) > 0.02:
                        _err(
                            f"[{rid}] partial_payment plan sums to {total:.2f}, "
                            f"expected {requested:.2f}"
                        )
                except (IndexError, ValueError):
                    pass

    # ── 0.7 Spending change format ─────────────────────────────────────────
    changes = row.get("spending_changes_needed", "")
    if changes and changes != "none":
        change_list = [c.strip() for c in changes.split("|")]
        if len(change_list) > 3:
            _err(f"[{rid}] spending_changes_needed has >3 entries: {changes}")
        seen_events = {}
        for c in change_list:
            if not SPENDING_CHANGE_RE.match(c):
                _err(f"[{rid}] Invalid spending_change entry: '{c}'")
                continue
            # Mutually exclusive per event
            parts = c.split(":")
            event_id = parts[1]
            action   = parts[0]
            if event_id in seen_events:
                _err(
                    f"[{rid}] Event {event_id} appears in multiple spending "
                    "change actions (must be mutually exclusive)"
                )
            seen_events[event_id] = action

    # ── earliest_date format ───────────────────────────────────────────────
    if earliest and not DATE_RE.match(earliest):
        _err(f"[{rid}] earliest_date_for_full_payment bad format: '{earliest}'")


def _print_result() -> None:
    if _warnings:
        print(f"\n{YELLOW}⚠  WARNINGS ({len(_warnings)}):{RESET}")
        for w in _warnings:
            print(f"  {YELLOW}• {w}{RESET}")

    if _errors:
        print(f"\n{RED}✗  VALIDATION FAILED — {len(_errors)} error(s):{RESET}")
        for e in _errors:
            print(f"  {RED}• {e}{RESET}")
    else:
        print(f"\n{GREEN}✓  VALIDATION PASSED — output.csv is submission-ready{RESET}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--output",   default="output.csv")
    p.add_argument("--requests", default="dataset/requests.csv")
    args = p.parse_args()

    ok = validate_output_csv(
        Path(args.output),
        Path(args.requests),
    )
    sys.exit(0 if ok else 1)
