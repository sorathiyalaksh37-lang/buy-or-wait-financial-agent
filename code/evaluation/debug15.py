import sys
from datetime import date
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_13")

print(f"Balance: {state.balance}")
print(f"Min balance: {state.min_balance}")
print(f"Available above min: {state.balance - state.min_balance}")
print()

# All settled income events
settled_income = [e for e in state.clean_events if e.direction == "credit" and e.status == "settled" and e.category in ("salary","income","freelance")]
settled_income.sort(key=lambda e: e.settlement_date)
if settled_income:
    import statistics
    gaps = [(settled_income[i+1].settlement_date - settled_income[i].settlement_date).days for i in range(len(settled_income)-1)]
    print(f"Income gaps: {gaps}")
    print(f"Last income: {settled_income[-1].settlement_date} amt={settled_income[-1].amount}")
    avg_gap = statistics.mean(gaps)
    print(f"Avg gap: {avg_gap:.1f}")
    from datetime import timedelta
    next_income_projected = settled_income[-1].settlement_date + timedelta(days=int(avg_gap))
    print(f"Next income projected on: {next_income_projected}")
