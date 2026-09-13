import sys
from datetime import date
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from forecaster import Forecaster
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)

# request_16: user_16, INR, balance=362370, min=122400, safe=0?
# That means forecaster thinks something will drain balance below 122400 before we can pay

state = ds.get_user_state("user_16")
fc = Forecaster(state, date(2023, 8, 12))  # request_date from sample

print("Balance:", state.balance)
print("Min balance:", state.min_balance)
print()
print("Daily flows:")
running = state.balance
for d, amounts in sorted(fc.daily_flows.items()):
    total = sum(amounts)
    running += total
    print(f"  {d}: {total:+.2f} => {running:.2f}")
