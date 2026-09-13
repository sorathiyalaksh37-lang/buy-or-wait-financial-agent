import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset, _parse_date
from forecaster import Forecaster
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_04")
fc = Forecaster(state, date(2024,6,4))

print(f"Balance={state.balance:,.0f}, min={state.min_balance:,.0f}")
print(f"Available above min: {state.balance - state.min_balance:,.0f}")
print()
print("All daily flows in the window:")
running = state.balance
for d, amounts in sorted(fc.daily_flows.items()):
    running += sum(amounts)
    print(f"  {d}: {sum(amounts):+,.0f} => {running:,.0f}")
    
print()
print("==> Without income, running balance:")
running = state.balance
for d, amounts in sorted(fc.daily_flows.items()):
    debits = [a for a in amounts if a < 0]
    running += sum(debits)
    print(f"  {d}: debits={sum(debits):+,.0f} => {running:,.0f}")
