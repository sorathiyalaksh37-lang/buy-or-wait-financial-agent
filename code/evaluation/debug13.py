import sys
from datetime import date
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)

state = ds.get_user_state("user_16")
print("Confirmed income events:")
for e in state.clean_events:
    if e.direction == "credit" and e.status in ("settled","scheduled"):
        print(f"  {e.event_date} {e.settlement_date} {e.status} {e.amount} {e.currency} {e.category}")
