"""
forecaster.py — Phase 3: 90-Day Cash-Flow Forecaster
Pure math simulation of user balances over time.
Checks if a proposed payment plan breaks the minimum balance requirement.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
import math
import itertools

from ingestion import (
    UserFinancialState,
    FinancialEvent,
    RecurringExpense,
)

# A payment plan is a list of (date, amount)
PaymentPlan = List[Tuple[date, float]]


@dataclass
class SpendingChange:
    action: str          # "stop" or "reduce_to"
    event_id: str
    new_amount: float    # 0.0 for stop, target amount for reduce_to


@dataclass
class SimulationResult:
    is_safe: bool
    witness_date: Optional[date]    # Date when balance dropped below min
    min_balance_reached: float      # The lowest balance hit


class Forecaster:
    def __init__(
        self,
        state: UserFinancialState,
        start_date: date,
        days: int = 90,
    ):
        self.state = state
        self.start_date = start_date
        self.end_date = start_date + timedelta(days=days)
        self.days = days
        
        # Pre-compute all known cash flows within the 90-day window
        self.daily_flows = self._build_daily_flows()

    def _build_daily_flows(self) -> Dict[date, List[float]]:
        """
        Builds a map of date -> list of amounts (positive for credit, negative for debit).
        Amounts are converted to home currency.
        """
        flows: Dict[date, List[float]] = defaultdict(list)
        
        # Build protected categories set
        protected = set(self.state.profile.expense_categories_to_protect)
        
        # 1. Future pending/scheduled events only.
        # IMPORTANT: settled events are already reflected in current_available_balance.
        # Only pending and scheduled events represent future cash-flows NOT yet in the balance.
        for evt in self.state.clean_events:
            # Skip settled events entirely - already in balance
            if evt.status == "settled":
                continue

            # Skip pending credits (rule: don't count pending credits)
            if evt.direction == "credit" and evt.status == "pending":
                continue

            if evt.amount is None:
                continue
                
            # Filter non-protected/non-essential debits
            if evt.direction == "debit":
                is_essential = evt.category in ("rent", "utilities", "insurance", "education", "healthcare", "debt_repayment", "family_support", "housing")
                is_protected = evt.category in protected
                if not (is_essential or is_protected):
                    continue

            amt = self.state.fx.convert(
                evt.amount, evt.currency, self.state.home_currency, evt.settlement_date
            )
            if amt is None:
                continue
                
            signed_amt = amt if evt.direction == "credit" else -amt
            
            # Apply on settlement_date (or start_date if overdue)
            apply_date = max(self.start_date, evt.settlement_date)
            if apply_date <= self.end_date:
                flows[apply_date].append(signed_amt)

        # 2. Recurring Expenses (essential/protected only)
        for rec in self.state.recurring_expenses:
            is_essential = rec.category in (
                "rent", "utilities", "insurance", "education", "healthcare",
                "debt_repayment", "family_support", "housing", "groceries", "transport"
            )
            is_protected = rec.category in protected
            if not (is_essential or is_protected):
                continue
                
            # Find the last settlement date for this recurring expense
            last_date = max(e.settlement_date for e in rec.sample_events)
            
            # Check if this expense has expired (no payment in > 1.5x cadence)
            # We use a minimum threshold of 40 days to be safe against slight delays.
            if (self.start_date - last_date).days > max(rec.cadence_days * 1.5, 40):
                continue
            
            # Project forward
            curr_date = last_date + timedelta(days=rec.cadence_days)
            while curr_date <= self.end_date:
                if curr_date >= self.start_date:
                    amt = self.state.fx.convert(
                        rec.avg_amount, rec.currency, self.state.home_currency, curr_date
                    )
                    if amt is not None:
                        flows[curr_date].append(-amt)
                curr_date += timedelta(days=rec.cadence_days)

        # 3. Recurring Income (salary, etc.)
        # Detect recurring income from settled salary events and project forward.
        income_events = [
            e for e in self.state.clean_events
            if e.direction == "credit" and e.status == "settled"
            and e.category in ("salary", "income", "freelance", "bonus")
            and e.amount is not None
        ]
        # Also include scheduled salary events
        scheduled_income = [
            e for e in self.state.clean_events
            if e.direction == "credit" and e.status == "scheduled"
            and e.category in ("salary", "income", "freelance", "bonus")
            and e.amount is not None
        ]
        if income_events:
            income_events.sort(key=lambda e: e.settlement_date)
            
            if len(income_events) >= 2:
                gaps = [
                    (income_events[i+1].settlement_date - income_events[i].settlement_date).days
                    for i in range(len(income_events)-1)
                ]
                avg_gap = int(sum(gaps) / len(gaps))
                income_currency = income_events[-1].currency
                
                # Detect if salary is monthly (same day-of-month)
                days_of_month = [e.settlement_date.day for e in income_events]
                most_common_day = max(set(days_of_month), key=days_of_month.count)
                day_consistency = days_of_month.count(most_common_day) / len(days_of_month)
                
                if day_consistency >= 0.6 and 25 <= avg_gap <= 60:
                    # Monthly salary on same day each month
                    # Sum up all payments in the last "month" as total monthly income
                    most_recent_day = income_events[-1].settlement_date.day
                    last_month_payments = [e for e in income_events if e.settlement_date.day == most_recent_day]
                    avg_income = sum(e.amount for e in last_month_payments) / len(last_month_payments) if last_month_payments else income_events[-1].amount
                    
                    # Find last occurrence at this day
                    last_on_day = income_events[-1].settlement_date
                    
                    # Project monthly: same day next months
                    import calendar
                    proj_month = last_on_day.month
                    proj_year = last_on_day.year
                    while True:
                        proj_month += 1
                        if proj_month > 12:
                            proj_month = 1
                            proj_year += 1
                        try:
                            next_income_date = date(proj_year, proj_month, most_recent_day)
                        except ValueError:
                            # Day doesn't exist in month (e.g. Feb 30)
                            last_day = calendar.monthrange(proj_year, proj_month)[1]
                            next_income_date = date(proj_year, proj_month, last_day)
                        
                        if next_income_date > self.end_date:
                            break
                        if next_income_date >= self.start_date:
                            # Skip if already scheduled
                            if not any(e.settlement_date == next_income_date for e in scheduled_income):
                                amt = self.state.fx.convert(
                                    avg_income, income_currency, self.state.home_currency, next_income_date
                                )
                                if amt is not None:
                                    flows[next_income_date].append(+amt)

                elif 5 <= avg_gap <= 24:
                    # Bi-weekly or split pay: aggregate into monthly buckets
                    # Sum all income events in last full month window
                    last_date = income_events[-1].settlement_date
                    window_start = last_date.replace(day=1)
                    monthly_total = sum(
                        e.amount for e in income_events
                        if e.settlement_date >= window_start
                    )
                    monthly_currency = income_events[-1].currency
                    
                    if monthly_total > 0:
                        import calendar
                        proj_month = last_date.month
                        proj_year = last_date.year
                        # Pay on 15th of each month as approximation
                        while True:
                            proj_month += 1
                            if proj_month > 12:
                                proj_month = 1
                                proj_year += 1
                            try:
                                next_income_date = date(proj_year, proj_month, 15)
                            except ValueError:
                                next_income_date = date(proj_year, proj_month, calendar.monthrange(proj_year, proj_month)[1])
                            if next_income_date > self.end_date:
                                break
                            if next_income_date >= self.start_date:
                                if not any(e.settlement_date == next_income_date for e in scheduled_income):
                                    amt = self.state.fx.convert(
                                        monthly_total, monthly_currency, self.state.home_currency, next_income_date
                                    )
                                    if amt is not None:
                                        flows[next_income_date].append(+amt)

        return flows

    def simulate(
        self, 
        plan: PaymentPlan, 
        spending_changes: Optional[List[SpendingChange]] = None
    ) -> SimulationResult:
        """
        Simulates the balance day-by-day.
        Returns whether the plan is safe (balance >= min_balance every day).
        """
        current_balance = self.state.balance
        min_balance = self.state.min_balance
        
        # Merge plan into flows
        sim_flows = defaultdict(list)
        for d, amounts in self.daily_flows.items():
            sim_flows[d].extend(amounts)
            
        for payment_date, payment_amt in plan:
            if payment_date <= self.end_date:
                sim_flows[payment_date].append(-payment_amt)
                
        # Apply spending changes
        if spending_changes:
            # Rebuilding flows is complex with changes, 
            # for now we'll do a simpler approach:
            # Identify which recurring expenses or specific events are modified
            # and adjust their flow.
            # To do this accurately, we should pass changes into _build_daily_flows.
            # But for simulation speed, let's rebuild custom flows if changes exist.
            sim_flows = self._build_daily_flows_with_changes(spending_changes)
            for payment_date, payment_amt in plan:
                if payment_date <= self.end_date:
                    sim_flows[payment_date].append(-payment_amt)

        lowest_balance = current_balance
        witness = None
        
        # Simulate day by day
        for i in range(self.days + 1):
            d = self.start_date + timedelta(days=i)
            if d in sim_flows:
                for amt in sim_flows[d]:
                    current_balance += amt
            
            if current_balance < lowest_balance:
                lowest_balance = current_balance
                
            # Floating point tolerance
            if current_balance < min_balance - 0.01:
                if witness is None:
                    witness = d
                    
        return SimulationResult(
            is_safe=(witness is None),
            witness_date=witness,
            min_balance_reached=lowest_balance
        )
        
    def _build_daily_flows_with_changes(self, changes: List[SpendingChange]) -> Dict[date, List[float]]:
        """Rebuilds flows applying spending changes to the events/recurring."""
        flows: Dict[date, List[float]] = defaultdict(list)
        
        # Create lookup for changes
        change_map = {c.event_id: c for c in changes}
        protected = set(self.state.profile.expense_categories_to_protect)
        
        for evt in self.state.clean_events:
            # Skip settled events — already in balance
            if evt.status == "settled":
                continue
            # Skip pending credits
            if evt.direction == "credit" and evt.status == "pending":
                continue
            if evt.amount is None:
                continue

            # Filter non-protected debits
            if evt.direction == "debit":
                is_essential = evt.category in ("rent", "utilities", "insurance", "education", "healthcare", "debt_repayment", "family_support", "housing")
                is_protected = evt.category in protected
                if not (is_essential or is_protected):
                    continue

            amt = evt.amount
            if evt.event_id in change_map:
                chg = change_map[evt.event_id]
                if chg.action == "stop":
                    continue
                elif chg.action == "reduce_to":
                    amt = chg.new_amount
                    
            conv_amt = self.state.fx.convert(
                amt, evt.currency, self.state.home_currency, evt.settlement_date
            )
            if conv_amt is None: continue
            
            signed_amt = conv_amt if evt.direction == "credit" else -conv_amt
            apply_date = max(self.start_date, evt.settlement_date)
            if apply_date <= self.end_date:
                flows[apply_date].append(signed_amt)

        for rec in self.state.recurring_expenses:
            is_essential = rec.category in (
                "rent", "utilities", "insurance", "education", "healthcare",
                "debt_repayment", "family_support", "housing", "groceries", "transport"
            )
            is_protected = rec.category in protected
            if not (is_essential or is_protected):
                continue
                
            # Check if this expense has expired
            last_date = max(e.settlement_date for e in rec.sample_events)
            if (self.start_date - last_date).days > max(rec.cadence_days * 1.5, 40):
                continue
                
            # If any of the recurring's sample events are stopped/reduced, apply to the projection
            rec_amt = rec.avg_amount
            for eid in rec.event_ids:
                if eid in change_map:
                    chg = change_map[eid]
                    if chg.action == "stop":
                        rec_amt = 0.0
                    elif chg.action == "reduce_to":
                        # Assume reduce_to is in the event's currency, which matches rec.currency
                        rec_amt = chg.new_amount

            if rec_amt <= 0:
                continue

            curr_date = last_date + timedelta(days=rec.cadence_days)
            while curr_date <= self.end_date:
                if curr_date >= self.start_date:
                    conv_amt = self.state.fx.convert(
                        rec_amt, rec.currency, self.state.home_currency, curr_date
                    )
                    if conv_amt is not None:
                        flows[curr_date].append(-conv_amt)
                curr_date += timedelta(days=rec.cadence_days)

        # Also project recurring income (same logic as main flow builder)
        income_events = [
            e for e in self.state.clean_events
            if e.direction == "credit" and e.status == "settled"
            and e.category in ("salary", "income", "freelance", "bonus")
            and e.amount is not None
        ]
        if income_events:
            income_events.sort(key=lambda e: e.settlement_date)
            if len(income_events) >= 2:
                gaps = [
                    (income_events[i+1].settlement_date - income_events[i].settlement_date).days
                    for i in range(len(income_events)-1)
                ]
                avg_gap = int(sum(gaps) / len(gaps))
                avg_income = sum(e.amount for e in income_events) / len(income_events)
                income_currency = income_events[-1].currency
                if 15 <= avg_gap <= 60:
                    last_income_date = income_events[-1].settlement_date
                    next_income_date = last_income_date + timedelta(days=avg_gap)
                    while next_income_date <= self.end_date:
                        if next_income_date >= self.start_date:
                            amt = self.state.fx.convert(
                                avg_income, income_currency, self.state.home_currency, next_income_date
                            )
                            if amt is not None:
                                flows[next_income_date].append(+amt)
                        next_income_date += timedelta(days=avg_gap)

        return flows

    def max_safe_lump_sum(self, on_date: date, cap: float) -> float:
        """
        Binary search the largest lump-sum on `on_date` that is safe.
        Returns amount between 0 and `cap`.
        This uses full simulation INCLUDING projected future income.
        """
        low = 0.0
        high = cap
        best = 0.0
        
        if not self.simulate([(on_date, 0.0)]).is_safe:
            return 0.0
            
        if self.simulate([(on_date, cap)]).is_safe:
            return cap
            
        while high - low > 0.01:
            mid = (low + high) / 2
            if self.simulate([(on_date, mid)]).is_safe:
                best = mid
                low = mid
            else:
                high = mid
                
        if best > 0.0:
            best = math.floor(best * 100) / 100.0
            
        return best

    def amount_safe_today(self, on_date: date, cap: float) -> float:
        """
        Per spec: amount_safe_to_pay = amount safe on request_date.
        Uses full simulation including projected future income.
        Delegates to max_safe_lump_sum.
        """
        return self.max_safe_lump_sum(on_date, cap)


    def earliest_safe_date(self, amount: float) -> Optional[date]:
        """
        Find the earliest date where `amount` can be safely paid as a lump sum.
        """
        for i in range(self.days + 1):
            d = self.start_date + timedelta(days=i)
            if self.simulate([(d, amount)]).is_safe:
                return d
        return None

    def find_safe_spending_changes(
        self, plan: PaymentPlan,
        allowed_categories_reduce: List[str],
        allowed_categories_stop: List[str]
    ) -> List[List[SpendingChange]]:
        """
        Generate subsets of up to 3 valid spending changes that make the plan safe.
        Returns a list of valid change combinations.
        """
        if self.simulate(plan).is_safe:
            return [[]] # Safe with no changes
            
        # Identify flexible events
        # Must be in allowed categories and have flexibility stop/reduce
        candidates = []
        seen_events = set()
        
        for evt in self.state.clean_events:
            if evt.direction != "debit": continue
            if evt.status not in ("settled", "scheduled", "pending"): continue
            
            # Can we stop it?
            if evt.category in allowed_categories_stop and evt.flexibility in ("stoppable", "reducible_or_stoppable"):
                if evt.event_id not in seen_events:
                    candidates.append(SpendingChange("stop", evt.event_id, 0.0))
                    
            # Can we reduce it?
            if evt.category in allowed_categories_reduce and evt.flexibility in ("reducible", "reducible_or_stoppable"):
                min_amt = evt.minimum_allowed_amount if evt.minimum_allowed_amount is not None else 0.0
                if evt.amount and evt.amount > min_amt:
                    candidates.append(SpendingChange("reduce_to", evt.event_id, min_amt))
                    
            seen_events.add(evt.event_id)
            
        # Also check recurring expenses
        for rec in self.state.recurring_expenses:
            if rec.category in allowed_categories_stop and rec.flexibility in ("stoppable", "reducible_or_stoppable"):
                for eid in rec.event_ids:
                    if eid not in seen_events:
                        candidates.append(SpendingChange("stop", eid, 0.0))
                        
            if rec.category in allowed_categories_reduce and rec.flexibility in ("reducible", "reducible_or_stoppable"):
                min_amt = rec.minimum_allowed_amount if rec.minimum_allowed_amount is not None else 0.0
                if rec.avg_amount > min_amt:
                    # Pick the last event to apply the change
                    if rec.event_ids:
                        eid = rec.event_ids[-1]
                        candidates.append(SpendingChange("reduce_to", eid, min_amt))

        # Filter out mutually exclusive candidates (same event id)
        # Generate combinations of size 1, 2, 3
        valid_combos = []
        
        for r in range(1, 4):
            for combo in itertools.combinations(candidates, r):
                # Check mutual exclusivity
                combo_eids = [c.event_id for c in combo]
                if len(set(combo_eids)) != len(combo_eids):
                    continue
                    
                if self.simulate(plan, list(combo)).is_safe:
                    valid_combos.append(list(combo))
                    
        return valid_combos
