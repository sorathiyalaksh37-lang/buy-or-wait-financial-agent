import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor
extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_24")
for r in state.recurring_expenses:
    is_essential = r.category in ("rent", "utilities", "insurance", "education", "healthcare", "debt_repayment", "family_support", "housing")
    is_protected = r.category in state.profile.expense_categories_to_protect
    if is_essential or is_protected:
        last_date = max(e.settlement_date for e in r.sample_events)
        print(f"Recurring {r.category}: {r.avg_amount}, last: {last_date}")
