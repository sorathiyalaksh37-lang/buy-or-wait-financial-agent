import sys
import csv
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
ds = load_dataset(Path("dataset"))
state = ds.get_user_state("user_01")
print(state.snapshot())
