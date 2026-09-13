import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor
extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_24")
import datetime
start_date = datetime.date(2026, 1, 4)
for r in state.recurring_expenses:
    if r.category not in ("entertainment", "dining", "shopping", "subscriptions"):
        last_date = max(e.settlement_date for e in r.sample_events)
        next_d = last_date + datetime.timedelta(days=r.cadence_days)
        while next_d <= start_date + datetime.timedelta(days=11):
            if next_d >= start_date:
                print(f"{r.category} {r.avg_amount} on {next_d}")
            next_d += datetime.timedelta(days=r.cadence_days)
