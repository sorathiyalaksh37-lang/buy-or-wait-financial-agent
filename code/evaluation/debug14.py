import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)

state = ds.get_user_state("user_13")
print("Profile:")
print("  protected:", state.profile.expense_categories_to_protect)
print("  reduce:", state.profile.expense_categories_user_is_willing_to_reduce)
print("  stop:", state.profile.expense_categories_user_is_willing_to_stop)
print()
print("Recurring:")
for r in state.recurring_expenses:
    print(f"  {r.category} ~{r.avg_amount:.2f} {r.currency} every {r.cadence_days}d")
