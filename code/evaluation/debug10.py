import sys
from datetime import date
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from forecaster import Forecaster
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)

import csv, re
from ingestion import Request, _parse_date, _parse_bool

for row in csv.DictReader(open("dataset/sample_requests.csv")):
    if row["request_id"] in ("request_14", "request_16", "request_19", "request_22", "request_23"):
        text = row.get("request_text", "").strip()
        m = re.search(r"([A-Z]{3})\s+[\d,\.]+", text)
        currency = m.group(1) if m else ""
        user_id = row["user_id"]
        req_date = _parse_date(row["request_date"])
        req_amt = float(row["requested_amount"])
        
        state = ds.get_user_state(user_id)
        fc = Forecaster(state, req_date)
        
        req_amt_home = state.fx.convert(req_amt, currency, state.home_currency, req_date)
        
        print(f"\n{row['request_id']}: user={user_id}, currency={currency}, home={state.home_currency}")
        print(f"  req_amt={req_amt}, req_amt_home={req_amt_home}")
        print(f"  balance={state.balance}, min_balance={state.min_balance}")
        print(f"  safe_today={fc.max_safe_lump_sum(req_date, req_amt_home or req_amt)}")
