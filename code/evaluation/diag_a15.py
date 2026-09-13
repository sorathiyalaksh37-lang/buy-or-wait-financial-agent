import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor
extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_24")
for e in state.clean_events:
    if e.direction == "credit" and e.category in ("salary", "income", "freelance", "bonus"):
        print(f"{e.settlement_date}: {e.amount} {e.currency} ({e.category}) - {e.status}")
