import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from extraction import Extractor
extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_24")
print("User 24 protected:", state.profile.expense_categories_to_protect)
print("User 24 adjustable:", state.profile.adjustable_categories)
