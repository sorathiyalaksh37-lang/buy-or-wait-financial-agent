"""
decision.py — Phase 4: Decision Policy & Plan Selection
Evaluates candidate plans, ranks them, maps statuses, and generates deterministic explanations.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Tuple, Dict
import copy

from ingestion import Request, PaymentOption, UserFinancialState, Dataset
from forecaster import Forecaster, PaymentPlan, SpendingChange
from schema import OutputRow

@dataclass
class EvaluatedPlan:
    method: str
    plan: PaymentPlan
    spending_changes: List[SpendingChange]
    total_cost: float
    completes_by_deadline: bool
    first_payment_date: date
    num_payments: int
    payment_option_id: str
    is_safe: bool

class DecisionEngine:
    def __init__(self, dataset: Dataset):
        self.dataset = dataset

    def process_request(self, req: Request) -> OutputRow:
        user_state = self.dataset.get_user_state(req.user_id)
        if not user_state:
            # Fallback if no user state
            return OutputRow(request_id=req.request_id)
            
        fc = Forecaster(user_state, req.request_date)
        
        req_currency = req.request_currency or user_state.home_currency
        
        # Convert requested amount to home currency for simulation
        req_amt_home = user_state.fx.convert(req.requested_amount, req_currency, user_state.home_currency, req.request_date)
        if req_amt_home is None:
            req_amt_home = req.requested_amount
            
        # 1. Base amounts
        # amount_safe_to_pay is "safe on request_date WITHOUT counting future income" (per spec)
        safe_today_home_conservative = fc.amount_safe_today(req.request_date, req_amt_home)
        # For plan eligibility (can we afford a plan considering future income?), use full simulation
        safe_today_home = fc.max_safe_lump_sum(req.request_date, req_amt_home)
        earliest_full = fc.earliest_safe_date(req_amt_home)
        
        candidates: List[EvaluatedPlan] = []
        
        allowed_methods = user_state.profile.payment_methods_user_will_consider
        
        # A) Full today
        if "full_payment" in allowed_methods:
            if safe_today_home >= req_amt_home:
                candidates.append(EvaluatedPlan(
                    method="full_payment",
                    plan=[(req.request_date, req.requested_amount)],
                    spending_changes=[],
                    total_cost=req.requested_amount,
                    completes_by_deadline=(req.request_date <= req.desired_completion_date),
                    first_payment_date=req.request_date,
                    num_payments=1,
                    payment_option_id="",
                    is_safe=True
                ))
            else:
                # B) Full today + spending changes
                changes = fc.find_safe_spending_changes(
                    [(req.request_date, req_amt_home)],
                    user_state.profile.expense_categories_user_is_willing_to_reduce,
                    user_state.profile.expense_categories_user_is_willing_to_stop
                )
                if changes:
                    # Pick minimal changes (fewest elements)
                    changes.sort(key=len)
                    best_change = changes[0]
                    candidates.append(EvaluatedPlan(
                        method="full_payment",
                        plan=[(req.request_date, req.requested_amount)],
                        spending_changes=best_change,
                        total_cost=req.requested_amount,
                        completes_by_deadline=(req.request_date <= req.desired_completion_date),
                        first_payment_date=req.request_date,
                        num_payments=1,
                        payment_option_id="",
                        is_safe=True
                    ))
                    
        # C) Partial
        # Convert CONSERVATIVE safe_today back to request_currency for amount_safe_to_pay
        safe_today = user_state.fx.convert(safe_today_home_conservative, user_state.home_currency, req_currency, req.request_date)
        if safe_today is None:
            safe_today = safe_today_home_conservative
        safe_today = min(safe_today, req.requested_amount)
            
        if "partial_payment" in allowed_methods and req.allows_partial_payment:
            if 0 < safe_today_home < req_amt_home and earliest_full:
                if earliest_full <= req.desired_completion_date:
                    partial_plan = [
                        (req.request_date, safe_today),
                        (earliest_full, req.requested_amount - safe_today)
                    ]
                    # Double check it's fully safe (simulate in home currency)
                    partial_plan_home = [
                        (req.request_date, safe_today_home),
                        (earliest_full, req_amt_home - safe_today_home)
                    ]
                    if fc.simulate(partial_plan_home).is_safe:
                        candidates.append(EvaluatedPlan(
                            method="partial_payment",
                            plan=partial_plan,
                            spending_changes=[],
                            total_cost=req.requested_amount,
                            completes_by_deadline=True,
                            first_payment_date=req.request_date,
                            num_payments=2,
                            payment_option_id="",
                            is_safe=True
                        ))

        # D) Installment Options
        if "installments" in allowed_methods:
            max_inst = user_state.profile.max_installment_months
            options = self.dataset.payment_options.get(req.request_id, [])
            for opt in options:
                if opt.payment_method == "installments":
                    if max_inst is not None and opt.number_of_payments > max_inst:
                        continue # Exceeds max months (rough check)
                        
                    # Build plan
                    inst_plan = []
                    inst_plan_home = []
                    d = opt.first_payment_date
                    freq = opt.payment_frequency_days or 30
                    for _ in range(opt.number_of_payments):
                        inst_plan.append((d, opt.payment_amount))
                        # For simulation, installments need to be converted to home currency too
                        opt_amt_home = user_state.fx.convert(opt.payment_amount, req_currency, user_state.home_currency, d)
                        inst_plan_home.append((d, opt_amt_home or opt.payment_amount))
                        d += timedelta(days=freq)
                        
                    last_date = inst_plan[-1][0]
                    
                    if last_date <= req.desired_completion_date and fc.simulate(inst_plan_home).is_safe:
                        candidates.append(EvaluatedPlan(
                            method="installments",
                            plan=inst_plan,
                            spending_changes=[],
                            total_cost=opt.total_payable_amount,
                            completes_by_deadline=(last_date <= req.desired_completion_date),
                            first_payment_date=opt.first_payment_date,
                            num_payments=opt.number_of_payments,
                            payment_option_id=opt.payment_option_id,
                            is_safe=True
                        ))

        # E) Wait — only if earliest_full is within desired_completion_date
        if "full_payment" in allowed_methods:
            if earliest_full and earliest_full > req.request_date:
                if earliest_full <= req.desired_completion_date:
                    candidates.append(EvaluatedPlan(
                        method="wait",
                        plan=[(earliest_full, req.requested_amount)],
                        spending_changes=[],
                        total_cost=req.requested_amount,
                        completes_by_deadline=True,
                        first_payment_date=earliest_full,
                        num_payments=1,
                        payment_option_id="",
                        is_safe=True
                    ))

        # F) Rank Candidates
        # Deterministic ranking:
        # 1) completes by deadline (True > False)
        # 2) no spending changes (True > False)
        # 3) minimize total paid (float asc)
        # 4) earlier start (date asc)
        # 5) fewer payments (int asc)
        # 6) lowest payment_option_id (str asc)
        
        valid = [c for c in candidates if c.is_safe]
        
        def sort_key(c: EvaluatedPlan):
            return (
                not c.completes_by_deadline,          # False first
                len(c.spending_changes) > 0,          # False first
                c.total_cost,
                c.first_payment_date,
                c.num_payments,
                c.payment_option_id
            )
            
        valid.sort(key=sort_key)
        
        out = OutputRow(
            request_id=req.request_id,
            amount_safe_to_pay=safe_today,
            earliest_date_for_full_payment=earliest_full.isoformat() if earliest_full else ""
        )
        
        if not valid:
            out.recommended_payment_method = "not_recommended"
            out.affordability_status = "not_affordable"
            out.payment_plan = "none"
            out.spending_changes_needed = "none"
            out.earliest_date_for_full_payment = ""  # Clear when not_affordable
        else:
            best = valid[0]
            out.recommended_payment_method = best.method
            
            # Format plan
            out.payment_plan = "|".join(f"{d.isoformat()}:{self._fmt(amt)}" for d, amt in best.plan)
            
            # Format spending changes
            if not best.spending_changes:
                out.spending_changes_needed = "none"
            else:
                chgs = []
                for chg in best.spending_changes:
                    if chg.action == "stop":
                        chgs.append(f"stop:{chg.event_id}")
                    else:
                        chgs.append(f"reduce_to:{chg.event_id}:{self._fmt(chg.new_amount)}")
                out.spending_changes_needed = "|".join(chgs)
                
            # Determine status
            if best.method == "full_payment" and not best.spending_changes and best.first_payment_date == req.request_date:
                out.affordability_status = "affordable_now"
            elif best.method == "wait" and earliest_full:
                out.affordability_status = "affordable_later"
            else:
                out.affordability_status = "affordable_with_plan"
                
        # Generate Explanation
        out.decision_explanation = self._generate_explanation(out, req, user_state)
        
        return out
        
    def _fmt(self, v: float) -> str:
        if v == int(v): return str(int(v))
        return f"{v:.2f}"
        
    def _generate_explanation(self, out: OutputRow, req: Request, state: UserFinancialState) -> str:
        curr = state.home_currency
        req_curr = req.request_currency or curr
        min_bal = self._fmt(state.min_balance)

        method = out.recommended_payment_method
        if method == "not_recommended":
            return f"Do not proceed with the {req_curr} {self._fmt(req.requested_amount)} request. Although {req_curr} {self._fmt(out.amount_safe_to_pay)} is available today, the full amount cannot be completed safely within 90 days."
            
        elif method == "full_payment":
            if out.spending_changes_needed != "none":
                return f"Make the required spending changes, then pay {req_curr} {self._fmt(req.requested_amount)} today. This leaves at least {curr} {min_bal} available."
            else:
                return f"Pay {req_curr} {self._fmt(req.requested_amount)} today. This leaves at least {curr} {min_bal} available over the next 90 days."
                
        elif method == "partial_payment":
            plan = out.payment_plan.split("|")
            p1_amt = plan[0].split(":")[1]
            p2_date = plan[1].split(":")[0]
            p2_amt = plan[1].split(":")[1]
            d2 = date.fromisoformat(p2_date).strftime("%-d %B %Y")
            return f"Pay {req_curr} {p1_amt} today and the remaining {req_curr} {p2_amt} on {d2}. This completes the full request and keeps the {curr} {min_bal} minimum protected."
            
        elif method == "installments":
            plan = out.payment_plan.split("|")
            n = len(plan)
            p1_date = plan[0].split(":")[0]
            p1_amt = plan[0].split(":")[1]
            d1 = date.fromisoformat(p1_date).strftime("%-d %B %Y")
            return f"Use {n} installments of {req_curr} {p1_amt}, starting {d1}. This leaves at least {curr} {min_bal} available."
            
        elif method == "wait":
            d1 = date.fromisoformat(out.earliest_date_for_full_payment).strftime("%-d %B %Y")
            return f"Wait until {d1}, then pay {req_curr} {self._fmt(req.requested_amount)} in full. Paying sooner would put the {curr} {min_bal} minimum at risk."
            
        return "Unknown decision."
