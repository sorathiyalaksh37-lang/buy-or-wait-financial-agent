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
    last_date = max(e.settlement_date for e in r.sample_events)
    gap = (start_date - last_date).days
    print(f"{r.category} {r.avg_amount} | Cadence {r.cadence_days} | Last {last_date} | Gap {gap}")
