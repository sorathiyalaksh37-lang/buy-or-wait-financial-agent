import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset, Request, _parse_date, _parse_bool
from forecaster import Forecaster
from decision import DecisionEngine
from extraction import Extractor
import csv, re

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
engine = DecisionEngine(ds)

def make_req(row):
    text = row.get("request_text","").strip()
    m = re.search(r"([A-Z]{3})\s+[\d,\.]+", text)
    return Request(
        request_id=row["request_id"],
        user_id=row["user_id"],
        request_date=_parse_date(row["request_date"]),
        request_type=row["request_type"],
        requested_amount=float(row["requested_amount"]),
        desired_completion_date=_parse_date(row["desired_completion_date"]),
        allows_partial_payment=_parse_bool(row.get("allows_partial_payment","false")),
        request_text=text,
        request_currency=m.group(1) if m else "",
    )

samples = {r["request_id"]: r for r in csv.DictReader(open("dataset/sample_requests.csv"))}

# --- Diagnostic A: request_04 ---
print("=== Diagnostic A: request_04 ===")
row04 = samples["request_04"]
req04 = make_req(row04)
state04 = ds.get_user_state(req04.user_id)
fc04 = Forecaster(state04, req04.request_date)

req_amt = req04.requested_amount
print(f"User: {req04.user_id}, balance={state04.balance}, min={state04.min_balance}")
print(f"Requested amount: {req_amt}")

print("\nDay-by-day from 2024-06-04 to 2024-06-20:")
running = state04.balance
for i in range(17):
    d = date(2024,6,4) + timedelta(days=i)
    day_flows = fc04.daily_flows.get(d, [])
    running += sum(day_flows)
    print(f"  {d}: flows={sum(day_flows):+.2f} bal={running:.2f}")

out04 = engine.process_request(req04)
print(f"\nAgent earliest_date: {out04.earliest_date_for_full_payment}")
print(f"Expected:            2024-06-15")

# --- Diagnostic B: request_01 and request_17 ---
print("\n=== Diagnostic B: explanation format ===")
for rid in ["request_01","request_17"]:
    row = samples[rid]
    req = make_req(row)
    out = engine.process_request(req)
    print(f"\n{rid}:")
    print(f"  Expected:  {row.get('decision_explanation','')}")
    print(f"  Actual:    {out.decision_explanation}")
