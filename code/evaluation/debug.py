import sys
import csv
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset, Request, _parse_date, _parse_bool
from forecaster import Forecaster

ds = load_dataset(Path("dataset"))
req_row = next(r for r in csv.DictReader(open("dataset/sample_requests.csv")) if r["request_id"] == "request_01")
req = Request(
    request_id=req_row["request_id"],
    user_id=req_row["user_id"],
    request_date=_parse_date(req_row["request_date"]),
    request_type=req_row["request_type"],
    requested_amount=float(req_row["requested_amount"]),
    desired_completion_date=_parse_date(req_row["desired_completion_date"]),
    allows_partial_payment=_parse_bool(req_row.get("allows_partial_payment", "false")),
    request_text=req_row.get("request_text", ""),
)

state = ds.get_user_state(req.user_id)
fc = Forecaster(state, req.request_date)

print(f"Start balance: {state.balance}")
print(f"Min balance: {state.min_balance}")
print(f"Safe amount: {fc.max_safe_lump_sum(req.request_date, req.requested_amount)}")
for i in range(10):
    res = fc.simulate([(req.request_date, i * 3000)])
    print(f"Simulate pay {i*3000}: safe={res.is_safe}, witness={res.witness_date}, min_reach={res.min_balance_reached}")
