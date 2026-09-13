import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor
extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_24")
for r in state.recurring_expenses:
    if r.category == "groceries" and abs(r.avg_amount - 2445.2) < 1:
        last_date = max(e.settlement_date for e in r.sample_events)
        print("Last date:", last_date)
