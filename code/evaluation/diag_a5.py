import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor
extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_04")
print("Profile protected:", state.profile.expense_categories_to_protect)
for r in state.recurring_expenses:
    print(f"Recurring {r.category}: {r.avg_amount} {r.currency} / {r.cadence_days}d (next expected: {r.next_expected_date})")
