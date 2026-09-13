import sys
from datetime import date
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from forecaster import Forecaster
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)

# Check user_13 (request_13 - EUR, expected safe=433.4)
import csv, re
from ingestion import _parse_date
for row in csv.DictReader(open("dataset/sample_requests.csv")):
    if row["request_id"] == "request_13":
        state = ds.get_user_state(row["user_id"])
        req_date = _parse_date(row["request_date"])
        fc = Forecaster(state, req_date)
        print(f"User: {row['user_id']}, balance={state.balance}, min={state.min_balance}")
        print(f"conservative safe: {fc.amount_safe_today(req_date, 1000)}")
        print(f"full safe: {fc.max_safe_lump_sum(req_date, 1000)}")
        print()
        print("Daily flows (debits only, for conservative):")
        running = state.balance
        for d, amounts in sorted(fc.daily_flows.items()):
            debits = [a for a in amounts if a < 0]
            credits = [a for a in amounts if a > 0]
            if debits or credits:
                print(f"  {d}: debits={sum(debits):.2f} credits={sum(credits):.2f} running={running + sum(debits):.2f}")
                running += sum(debits) + sum(credits)
        break
