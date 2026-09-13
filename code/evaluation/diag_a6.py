import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor
extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_04")
for e in state.clean_events:
    if e.status in ("pending", "scheduled"):
        print(f"{e.status} {e.direction} {e.category} {e.amount} {e.currency} on {e.settlement_date}")
