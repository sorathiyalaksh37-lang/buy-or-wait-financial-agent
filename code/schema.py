"""
schema.py — Phase 0.1: Single source of truth for output schema.
All column names, enums, and field rules live here.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

# ── Output schema ──────────────────────────────────────────────────────────────
OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]

AFFORDABILITY_STATUSES = frozenset({
    "affordable_now",
    "affordable_with_plan",
    "affordable_later",
    "not_affordable",
})

PAYMENT_METHODS = frozenset({
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
    "not_recommended",
})

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PAYMENT_PLAN_ENTRY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}:\d+(\.\d+)?$")
SPENDING_CHANGE_RE = re.compile(
    r"^(stop:[a-zA-Z0-9_]+|reduce_to:[a-zA-Z0-9_]+:\d+(\.\d+)?)$"
)


@dataclass
class OutputRow:
    """Typed output row — single source of truth."""
    request_id: str
    amount_safe_to_pay: float = 0.0
    affordability_status: str = "not_affordable"
    recommended_payment_method: str = "not_recommended"
    payment_plan: str = "none"
    earliest_date_for_full_payment: str = ""      # may be blank
    spending_changes_needed: str = "none"
    decision_explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "amount_safe_to_pay": _fmt_amount(self.amount_safe_to_pay),
            "affordability_status": self.affordability_status,
            "recommended_payment_method": self.recommended_payment_method,
            "payment_plan": self.payment_plan,
            "earliest_date_for_full_payment": self.earliest_date_for_full_payment,
            "spending_changes_needed": self.spending_changes_needed,
            "decision_explanation": self.decision_explanation,
        }


def _fmt_amount(v: float) -> str:
    """Format amount — up to 2 decimal places, no trailing zeros beyond .xx."""
    if v == int(v):
        return str(int(v))
    return f"{v:.2f}"
