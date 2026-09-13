import sys
import csv
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset, Request, _parse_date, _parse_bool, ESSENTIAL_CATEGORIES
from forecaster import Forecaster

ds = load_dataset(Path("dataset"))
req_row = next(r for r in csv.DictReader(open("dataset/sample_requests.csv")) if r["request_id"] == "request_01")
state = ds.get_user_state(req_row["user_id"])

protected = ESSENTIAL_CATEGORIES | set(state.profile.expense_categories_to_protect)

print("Projected expenses:")
for rec in state.recurring_expenses:
    if rec.category in protected:
        print(f"PROTECTED: {rec.category} {rec.avg_amount}")
    else:
        print(f"IGNORED: {rec.category} {rec.avg_amount}")

