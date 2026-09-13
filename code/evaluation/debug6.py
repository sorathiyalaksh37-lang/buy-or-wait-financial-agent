import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)

import csv
for row in csv.DictReader(open("dataset/sample_requests.csv")):
    if row["request_id"] == "request_17":
        user_id = row["user_id"]
        state = ds.get_user_state(user_id)
        print("User:", user_id)
        print("Home Currency:", state.home_currency)
        print("Balance:", state.balance)
        for e in state.clean_events:
            print(f"{e.event_date} {e.direction} {e.amount} {e.currency} {e.status} {e.category} {e.event_id} linked:{e.linked_event_id}")
        break
