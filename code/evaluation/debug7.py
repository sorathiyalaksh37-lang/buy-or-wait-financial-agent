import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)

state = ds.get_user_state("user_17")
for e in state.clean_events:
    if e.event_id == "event_1545":
        print(f"event_1545 amount: {e.amount}")
