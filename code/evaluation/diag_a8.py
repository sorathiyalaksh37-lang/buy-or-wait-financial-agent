import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor
extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_24")
print("Pending/Scheduled:")
for e in state.clean_events:
    if e.status in ("pending", "scheduled"):
        print(f"{e.status} {e.direction} {e.category} {e.amount} {e.currency} on {e.settlement_date}")
print("\nRecurring:")
for r in state.recurring_expenses:
    print(f"Recurring {r.category}: {r.avg_amount} {r.currency} / {r.cadence_days}d")
