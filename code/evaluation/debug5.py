import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from decision import DecisionEngine
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
engine = DecisionEngine(ds)

import csv
from ingestion import Request, _parse_date, _parse_bool
import re
req = None
for row in csv.DictReader(open("dataset/sample_requests.csv")):
    if row["request_id"] == "request_17":
        text = row.get("request_text", "").strip()
        m = re.search(r"([A-Z]{3})\s+[\d,\.]+", text)
        currency = m.group(1) if m else ""
        req = Request(
            request_id=row["request_id"].strip(),
            user_id=row["user_id"].strip(),
            request_date=_parse_date(row["request_date"]),
            request_type=row["request_type"].strip(),
            requested_amount=float(row["requested_amount"]),
            desired_completion_date=_parse_date(row["desired_completion_date"]),
            allows_partial_payment=_parse_bool(row.get("allows_partial_payment", "false")),
            request_text=text,
            request_currency=currency,
        )
        break

out = engine.process_request(req)
print("Amount safe:", out.amount_safe_to_pay)
print("Expected: 243849.58")
