import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset, Request, _parse_date, _parse_bool
from forecaster import Forecaster
from extraction import Extractor
import csv, re

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state04 = ds.get_user_state("user_04")
fc04 = Forecaster(state04, date(2024,6,4))

# simulate paying 12693000 on each day 04 to 20
print("Simulate paying 12693000 on each day:")
for i in range(17):
    d = date(2024,6,4) + timedelta(days=i)
    res = fc04.simulate([(d, 12693000)])
    print(f"  {d}: safe={res.is_safe}, witness={res.witness_date}, min_reach={res.min_balance_reached:.0f}")
