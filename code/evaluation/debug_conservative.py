import sys, math
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from forecaster import Forecaster
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)

import csv
from ingestion import _parse_date
for row in csv.DictReader(open("dataset/sample_requests.csv")):
    if row["request_id"] == "request_13":
        state = ds.get_user_state(row["user_id"])
        req_date = _parse_date(row["request_date"])
        fc = Forecaster(state, req_date)
        
        # Replicate amount_safe_today logic
        no_income_flows = defaultdict(list)
        for d, amounts in fc.daily_flows.items():
            filtered = [a for a in amounts if a < 0]
            if filtered:
                no_income_flows[d] = filtered
        
        print("No-income flows:")
        running = state.balance
        for d in sorted(no_income_flows.keys()):
            total = sum(no_income_flows[d])
            running += total
            print(f"  {d}: {total:.2f} => {running:.2f} (min={state.min_balance})")
        break
