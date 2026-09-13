import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor
extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_24")
for e in state.clean_events:
    if e.direction == "debit" and e.status in ("pending", "scheduled"):
        conv = state.fx.convert(e.amount, e.currency, state.home_currency, e.settlement_date)
        print(f"Scheduled debit: {e.amount} {e.currency} -> {conv} {state.home_currency}")
for r in state.recurring_expenses:
    conv = state.fx.convert(r.avg_amount, r.currency, state.home_currency, r.sample_events[-1].settlement_date)
    print(f"Recurring {r.category}: {r.avg_amount} {r.currency} -> {conv} {state.home_currency}")
