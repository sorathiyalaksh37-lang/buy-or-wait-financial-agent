import sys
from datetime import date
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from ingestion import load_dataset
from decision import DecisionEngine
from forecaster import Forecaster
from extraction import Extractor

extractor = Extractor()
ds = load_dataset(Path("dataset"), extractor)
state = ds.get_user_state("user_17")
fc = Forecaster(state, date.fromisoformat("2026-02-15"))

# Print daily flows
for d, amounts in sorted(fc.daily_flows.items()):
    print(f"{d}: {sum(amounts)}")

