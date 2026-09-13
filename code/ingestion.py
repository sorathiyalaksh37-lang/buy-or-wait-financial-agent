"""
ingestion.py — Phase 1: Load all dataset files into typed dataclasses.
Handles date parsing, currency conversion, event hygiene, recurrence detection,
and user profile assembly.
"""

from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# 1. Typed dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FinancialProfile:
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    financial_priorities: List[str]
    expense_categories_to_protect: List[str]
    expense_categories_user_is_willing_to_reduce: List[str]
    expense_categories_user_is_willing_to_stop: List[str]
    payment_methods_user_will_consider: List[str]
    max_installment_months: Optional[int]  # None = no installments


@dataclass
class FinancialEvent:
    event_id: str
    user_id: str
    event_type: str            # expense | income | investment_purchase | investment_sale | investment_valuation | transfer
    description: str
    category: str
    direction: str             # debit | credit
    amount: Optional[float]    # None = blank (needs image extraction)
    currency: str
    event_date: date
    settlement_date: date
    status: str                # settled | pending | scheduled | failed | cancelled | unrealized
    linked_event_id: Optional[str]
    flexibility: str           # fixed | stoppable | reducible | reducible_or_stoppable
    minimum_allowed_amount: Optional[float]


@dataclass
class ExchangeRate:
    rate_date: date
    from_currency: str
    to_currency: str
    rate: float


@dataclass
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: float
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str


@dataclass
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str           # full_payment | installments
    payment_amount: float
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: Optional[int]
    financing_fee: float
    total_payable_amount: float


@dataclass
class Message:
    message_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    sent_at: str
    source_type: str
    message_text: str


@dataclass
class ImageRecord:
    image_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(s: str) -> date:
    """Strict YYYY-MM-DD parse."""
    return date.fromisoformat(s.strip())


def _parse_optional_float(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_bool(s: str) -> bool:
    return s.strip().lower() in ("true", "1", "yes")


def _pipe_list(s: str) -> List[str]:
    s = s.strip()
    if not s:
        return []
    return [x.strip() for x in s.split("|") if x.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# 3. CSV loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_profiles(path: Path) -> Dict[str, FinancialProfile]:
    profiles: Dict[str, FinancialProfile] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            uid = row["user_id"].strip()
            max_inst = None
            raw_mi = row.get("max_installment_months", "").strip()
            if raw_mi:
                try:
                    max_inst = int(raw_mi)
                except ValueError:
                    pass
            profiles[uid] = FinancialProfile(
                user_id=uid,
                home_currency=row["home_currency"].strip(),
                current_available_balance=float(row["current_available_balance"]),
                minimum_balance_to_keep=float(row["minimum_balance_to_keep"]),
                financial_priorities=_pipe_list(row.get("financial_priorities", "")),
                expense_categories_to_protect=_pipe_list(row.get("expense_categories_to_protect", "")),
                expense_categories_user_is_willing_to_reduce=_pipe_list(row.get("expense_categories_user_is_willing_to_reduce", "")),
                expense_categories_user_is_willing_to_stop=_pipe_list(row.get("expense_categories_user_is_willing_to_stop", "")),
                payment_methods_user_will_consider=_pipe_list(row.get("payment_methods_user_will_consider", "")),
                max_installment_months=max_inst,
            )
    return profiles


def load_events(path: Path) -> Dict[str, List[FinancialEvent]]:
    """Returns dict[user_id -> sorted list of events]."""
    by_user: Dict[str, List[FinancialEvent]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            evt = FinancialEvent(
                event_id=row["event_id"].strip(),
                user_id=row["user_id"].strip(),
                event_type=row["event_type"].strip(),
                description=row.get("description", "").strip(),
                category=row.get("category", "").strip(),
                direction=row["direction"].strip(),
                amount=_parse_optional_float(row.get("amount", "")),
                currency=row["currency"].strip(),
                event_date=_parse_date(row["event_date"]),
                settlement_date=_parse_date(row["settlement_date"] if row["settlement_date"].strip() else row["event_date"]),
                status=row["status"].strip(),
                linked_event_id=row.get("linked_event_id", "").strip() or None,
                flexibility=row.get("flexibility", "fixed").strip() or "fixed",
                minimum_allowed_amount=_parse_optional_float(row.get("minimum_allowed_amount", "")),
            )
            by_user[evt.user_id].append(evt)
    # Sort by settlement_date, then event_id for determinism
    for uid in by_user:
        by_user[uid].sort(key=lambda e: (e.settlement_date, e.event_id))
    return dict(by_user)


def load_exchange_rates(path: Path) -> List[ExchangeRate]:
    rates: List[ExchangeRate] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rates.append(ExchangeRate(
                rate_date=_parse_date(row["rate_date"]),
                from_currency=row["from_currency"].strip(),
                to_currency=row["to_currency"].strip(),
                rate=float(row["rate"]),
            ))
    rates.sort(key=lambda r: r.rate_date)
    return rates


def load_requests(path: Path) -> List[Request]:
    reqs: List[Request] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            reqs.append(Request(
                request_id=row["request_id"].strip(),
                user_id=row["user_id"].strip(),
                request_date=_parse_date(row["request_date"]),
                request_type=row["request_type"].strip(),
                requested_amount=float(row["requested_amount"]),
                desired_completion_date=_parse_date(row["desired_completion_date"]),
                allows_partial_payment=_parse_bool(row.get("allows_partial_payment", "false")),
                request_text=row.get("request_text", "").strip(),
            ))
    return reqs


def load_payment_options(path: Path) -> Dict[str, List[PaymentOption]]:
    """Returns dict[request_id -> list of PaymentOption]."""
    by_request: Dict[str, List[PaymentOption]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            freq = row.get("payment_frequency_days", "").strip()
            opt = PaymentOption(
                payment_option_id=row["payment_option_id"].strip(),
                request_id=row["request_id"].strip(),
                payment_method=row["payment_method"].strip(),
                payment_amount=float(row["payment_amount"]),
                number_of_payments=int(row["number_of_payments"]),
                first_payment_date=_parse_date(row["first_payment_date"]),
                payment_frequency_days=int(freq) if freq else None,
                financing_fee=float(row.get("financing_fee", "0") or "0"),
                total_payable_amount=float(row["total_payable_amount"]),
            )
            by_request[opt.request_id].append(opt)
    return dict(by_request)


def load_messages(path: Path) -> Dict[str, List[Message]]:
    """Returns dict[user_id -> list of Message]."""
    by_user: Dict[str, List[Message]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m = Message(
                message_id=row["message_id"].strip(),
                user_id=row["user_id"].strip(),
                request_id=row.get("request_id", "").strip() or None,
                related_event_id=row.get("related_event_id", "").strip() or None,
                sent_at=row.get("sent_at", "").strip(),
                source_type=row.get("source_type", "").strip(),
                message_text=row.get("message_text", "").strip(),
            )
            by_user[m.user_id].append(m)
    return dict(by_user)


def load_images(path: Path) -> Dict[str, List[ImageRecord]]:
    """Returns dict[user_id -> list of ImageRecord]."""
    by_user: Dict[str, List[ImageRecord]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            img = ImageRecord(
                image_id=row["image_id"].strip(),
                user_id=row["user_id"].strip(),
                request_id=row.get("request_id", "").strip() or None,
                related_event_id=row.get("related_event_id", "").strip() or None,
            )
            by_user[img.user_id].append(img)
    return dict(by_user)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Exchange rate lookup (Phase 1.3)
# ─────────────────────────────────────────────────────────────────────────────

class ExchangeRateIndex:
    """
    Given a list of ExchangeRate rows, resolve from_currency → to_currency
    on or before a given date (carry-forward closest prior rate).
    Also supports chained conversion via a common base.
    """

    def __init__(self, rates: List[ExchangeRate]) -> None:
        # key: (from_currency, to_currency) → sorted list of (date, rate)
        self._index: Dict[Tuple[str, str], List[Tuple[date, float]]] = defaultdict(list)
        for r in rates:
            self._index[(r.from_currency, r.to_currency)].append((r.rate_date, r.rate))
        for key in self._index:
            self._index[key].sort(key=lambda x: x[0])

    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        on_date: date,
    ) -> Optional[float]:
        """Return best available rate on or before on_date. None if not found."""
        if from_currency == to_currency:
            return 1.0

        pair = (from_currency, to_currency)
        if pair in self._index:
            return self._lookup(pair, on_date)

        # Try inverse
        inv = (to_currency, from_currency)
        if inv in self._index:
            r = self._lookup(inv, on_date)
            return (1.0 / r) if r else None

        # Try chain through any common currency
        from_pairs = {k[1]: k for k in self._index if k[0] == from_currency}
        to_pairs   = {k[0]: k for k in self._index if k[1] == to_currency}
        common = set(from_pairs) & set(to_pairs)
        if common:
            mid = next(iter(common))
            r1 = self._lookup(from_pairs[mid], on_date)
            r2 = self._lookup(to_pairs[mid], on_date)
            if r1 and r2:
                return r1 * r2

        return None

    def _lookup(self, pair: Tuple[str, str], on_date: date) -> Optional[float]:
        entries = self._index[pair]
        best = None
        for d, r in entries:
            if d <= on_date:
                best = r
            else:
                break
        return best

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        on_date: date,
    ) -> Optional[float]:
        rate = self.get_rate(from_currency, to_currency, on_date)
        if rate is None:
            return None
        return amount * rate


# ─────────────────────────────────────────────────────────────────────────────
# 5. Transaction hygiene (Phase 1B)
# ─────────────────────────────────────────────────────────────────────────────

CASH_STATUSES = frozenset({"settled", "pending", "scheduled"})
NON_CASH_STATUSES = frozenset({"failed", "cancelled", "unrealized"})
NON_CASH_TYPES = frozenset({"investment_valuation"})


def is_cash_event(evt: FinancialEvent) -> bool:
    """True if the event contributes to cash flow."""
    if evt.event_type in NON_CASH_TYPES:
        return False
    if evt.status in NON_CASH_STATUSES:
        return False
    if evt.status not in CASH_STATUSES:
        return False
    return True


def clean_events(events: List[FinancialEvent]) -> List[FinancialEvent]:
    """
    Phase 1.6–1.7: Filter and de-duplicate events.
    - Keep only cash events
    - When linked_event_id present and the linked event fully offsets (same amount, opposite direction),
      skip the later event that is a refund/cancel for an already-excluded event.
    - Failed events: exclude unless there is a linked retry that is scheduled/settled.
    """
    by_id: Dict[str, FinancialEvent] = {e.event_id: e for e in events}
    excluded: Set[str] = set()

    # Mark failed events excluded unless linked retry exists
    for evt in events:
        if evt.status == "failed":
            # Find if there's a linked retry
            has_retry = any(
                e.linked_event_id == evt.event_id and e.status in ("scheduled", "settled", "pending")
                for e in events
            )
            if has_retry:
                # The failed event is superseded by its retry; exclude the failed one
                excluded.add(evt.event_id)
            else:
                excluded.add(evt.event_id)

    # Cancelled auth + settled purchase: exclude the cancelled one
    for evt in events:
        if evt.status == "cancelled" and evt.linked_event_id:
            linked = by_id.get(evt.linked_event_id)
            if linked and linked.status == "settled":
                excluded.add(evt.event_id)
        if evt.status == "cancelled":
            excluded.add(evt.event_id)

    # Build final list
    result = []
    for evt in events:
        if evt.event_id in excluded:
            continue
        if not is_cash_event(evt):
            continue
        result.append(evt)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 6. Recurrence detection (Phase 1C)
# ─────────────────────────────────────────────────────────────────────────────

ESSENTIAL_CATEGORIES = frozenset({
    "rent", "utilities", "insurance", "education", "healthcare",
    "debt_repayment", "family_support", "housing",
})

DISCRETIONARY_CATEGORIES = frozenset({
    "dining", "entertainment", "shopping", "groceries", "delivery_membership",
    "cloud_storage", "streaming", "subscriptions",
})


@dataclass
class RecurringExpense:
    category: str
    description: str
    avg_amount: float          # In user's home currency
    currency: str
    cadence_days: int          # Approx days between payments
    is_essential: bool
    sample_events: List[FinancialEvent]   # The events that triggered detection
    flexibility: str
    minimum_allowed_amount: Optional[float]
    event_ids: List[str]


def detect_recurring_expenses(
    events: List[FinancialEvent],
    home_currency: str,
    fx: ExchangeRateIndex,
) -> List[RecurringExpense]:
    """
    Phase 1.11: Group debit events by (category, description_prefix) and detect
    monthly cadence. Returns list of detected recurring expenses.
    """
    # Group settled/scheduled debits by category+description
    groups: Dict[str, List[FinancialEvent]] = defaultdict(list)
    for e in events:
        if e.direction != "debit":
            continue
        if e.status not in ("settled", "scheduled"):
            continue
        if e.event_type not in ("expense", "transfer"):
            continue
        if e.amount is None:
            continue
        key = f"{e.category}||{_normalize_desc(e.description)}"
        groups[key].append(e)

    recurring = []
    for key, evts in groups.items():
        if len(evts) < 2:
            continue
        evts_sorted = sorted(evts, key=lambda e: e.settlement_date)
        # Check cadence
        gaps = []
        for i in range(1, len(evts_sorted)):
            gap = (evts_sorted[i].settlement_date - evts_sorted[i-1].settlement_date).days
            gaps.append(gap)
        avg_gap = sum(gaps) / len(gaps)
        # Allow 20–45 days as "monthly", 6-10 as weekly
        if not (18 <= avg_gap <= 50):
            continue
        # Check amount consistency (within 20%)
        amounts = [e.amount for e in evts_sorted if e.amount]
        if not amounts:
            continue
        avg_amt = sum(amounts) / len(amounts)
        spread = max(amounts) - min(amounts)
        if avg_amt > 0 and spread / avg_amt > 0.5:
            continue  # too variable

        category = evts_sorted[0].category
        recurring.append(RecurringExpense(
            category=category,
            description=evts_sorted[0].description,
            avg_amount=avg_amt,
            currency=evts_sorted[0].currency,
            cadence_days=round(avg_gap),
            is_essential=category in ESSENTIAL_CATEGORIES,
            sample_events=evts_sorted[-3:],
            flexibility=evts_sorted[-1].flexibility,
            minimum_allowed_amount=evts_sorted[-1].minimum_allowed_amount,
            event_ids=[e.event_id for e in evts_sorted],
        ))

    return recurring


def _normalize_desc(desc: str) -> str:
    """Strip variable parts from description for grouping."""
    # Remove numbers and common variable tokens
    desc = re.sub(r"\d+", "", desc.lower())
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc[:40]


# ─────────────────────────────────────────────────────────────────────────────
# 7. User financial state (Phase 1D)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class UserFinancialState:
    profile: FinancialProfile
    clean_events: List[FinancialEvent]     # Filtered, sorted by settlement_date
    recurring_expenses: List[RecurringExpense]
    messages: List[Message]
    images: List[ImageRecord]
    fx: ExchangeRateIndex

    @property
    def user_id(self) -> str:
        return self.profile.user_id

    @property
    def home_currency(self) -> str:
        return self.profile.home_currency

    @property
    def balance(self) -> float:
        return self.profile.current_available_balance

    @property
    def min_balance(self) -> float:
        return self.profile.minimum_balance_to_keep

    def snapshot(self) -> str:
        """Plain-English financial snapshot for debugging (Phase 1 exit criterion)."""
        lines = [
            f"User: {self.user_id}",
            f"  Home currency:   {self.home_currency}",
            f"  Balance:         {self.balance:,.2f} {self.home_currency}",
            f"  Min balance:     {self.min_balance:,.2f} {self.home_currency}",
            f"  Available:       {self.balance - self.min_balance:,.2f} {self.home_currency}",
            f"  Payment methods: {self.profile.payment_methods_user_will_consider}",
            f"  Priorities:      {self.profile.financial_priorities}",
            f"  Recurring ({len(self.recurring_expenses)}):",
        ]
        for r in self.recurring_expenses[:5]:
            lines.append(
                f"    [{r.category}] {r.description[:30]} "
                f"~{r.avg_amount:.0f} {r.currency} every {r.cadence_days}d "
                f"({'essential' if r.is_essential else 'discretionary'})"
            )
        # Upcoming settled credits (income)
        income_evts = [
            e for e in self.clean_events
            if e.direction == "credit"
            and e.status in ("scheduled", "settled")
            and e.event_type in ("income", "salary")
            and e.amount
        ]
        if income_evts:
            lines.append(f"  Confirmed income ({len(income_evts)} events):")
            for e in income_evts[-3:]:
                lines.append(
                    f"    {e.settlement_date} {e.amount:.2f} {e.currency} [{e.status}]"
                )
        return "\n".join(lines)


def build_user_state(
    user_id: str,
    profiles: Dict[str, FinancialProfile],
    all_events: Dict[str, List[FinancialEvent]],
    messages: Dict[str, List[Message]],
    images: Dict[str, List[ImageRecord]],
    fx: ExchangeRateIndex,
) -> Optional[UserFinancialState]:
    profile = profiles.get(user_id)
    if profile is None:
        return None

    raw_events = all_events.get(user_id, [])
    cleaned = clean_events(raw_events)
    recurring = detect_recurring_expenses(cleaned, profile.home_currency, fx)

    return UserFinancialState(
        profile=profile,
        clean_events=cleaned,
        recurring_expenses=recurring,
        messages=messages.get(user_id, []),
        images=images.get(user_id, []),
        fx=fx,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. Full dataset loader
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Dataset:
    requests: List[Request]
    profiles: Dict[str, FinancialProfile]
    all_events: Dict[str, List[FinancialEvent]]
    fx: ExchangeRateIndex
    payment_options: Dict[str, List[PaymentOption]]
    messages: Dict[str, List[Message]]
    images: Dict[str, List[ImageRecord]]
    dataset_root: Path
    _user_states: Dict[str, UserFinancialState] = field(default_factory=dict)

    def get_user_state(self, user_id: str) -> Optional[UserFinancialState]:
        if user_id not in self._user_states:
            state = build_user_state(
                user_id, self.profiles, self.all_events,
                self.messages, self.images, self.fx,
            )
            if state:
                self._user_states[user_id] = state
        return self._user_states.get(user_id)

    def image_path(self, image_id: str) -> Path:
        return self.dataset_root / "media" / "images" / f"{image_id}.png"


def load_dataset(dataset_root: Path) -> Dataset:
    print(f"[ingestion] Loading dataset from {dataset_root} …")
    profiles = load_profiles(dataset_root / "financial_profiles.csv")
    print(f"  profiles: {len(profiles)}")
    all_events = load_events(dataset_root / "financial_events.csv")
    print(f"  event users: {len(all_events)}")
    rates = load_exchange_rates(dataset_root / "exchange_rates.csv")
    print(f"  exchange rates: {len(rates)}")
    fx = ExchangeRateIndex(rates)
    requests = load_requests(dataset_root / "requests.csv")
    print(f"  requests: {len(requests)}")
    payment_options = load_payment_options(dataset_root / "request_payment_options.csv")
    print(f"  payment option groups: {len(payment_options)}")
    messages = load_messages(dataset_root / "messages.csv")
    print(f"  message users: {len(messages)}")
    images = load_images(dataset_root / "images.csv")
    print(f"  image users: {len(images)}")
    return Dataset(
        requests=requests,
        profiles=profiles,
        all_events=all_events,
        fx=fx,
        payment_options=payment_options,
        messages=messages,
        images=images,
        dataset_root=dataset_root,
    )
