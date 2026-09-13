"""
evaluator.py — Phase 5: Evaluation Harness
Runs the agent on sample_requests.csv, diffs against expected, and calculates per-field match rate.
"""

from __future__ import annotations
import csv
import sys
from pathlib import Path
from typing import Dict, List, Any

# Adjust path to import from code/
sys.path.append(str(Path(__file__).parent.parent))

from schema import OutputRow, OUTPUT_COLUMNS
from ingestion import load_dataset
from decision import DecisionEngine

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def load_expected(path: Path) -> Dict[str, dict]:
    expected = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            expected[row["request_id"]] = row
    return expected

def evaluate(dataset_path: Path, sample_path: Path):
    print("Loading dataset...")
    ds = load_dataset(dataset_path)
    expected = load_expected(sample_path)
    
    engine = DecisionEngine(ds)
    
    # Filter dataset requests to only those in the sample expected set,
    # Actually, sample_requests.csv acts as BOTH the requests AND expected outputs.
    sample_requests = []
    from ingestion import Request, _parse_date, _parse_bool
    for req_id, row in expected.items():
        req = Request(
            request_id=row["request_id"].strip(),
            user_id=row["user_id"].strip(),
            request_date=_parse_date(row["request_date"]),
            request_type=row["request_type"].strip(),
            requested_amount=float(row["requested_amount"]),
            desired_completion_date=_parse_date(row["desired_completion_date"]),
            allows_partial_payment=_parse_bool(row.get("allows_partial_payment", "false")),
            request_text=row.get("request_text", "").strip(),
        )
        sample_requests.append(req)
        
    print(f"Evaluating {len(sample_requests)} sample requests...")
    
    metrics = {col: {"matches": 0, "total": 0} for col in OUTPUT_COLUMNS if col != "request_id"}
    
    for req in sample_requests:
        exp = expected[req.request_id]
        
        # Run agent
        try:
            actual_row = engine.process_request(req)
            actual = actual_row.to_dict()
        except Exception as e:
            print(f"{RED}Error processing {req.request_id}: {e}{RESET}")
            continue
            
        # Compare
        for col in metrics:
            metrics[col]["total"] += 1
            e_val = exp.get(col, "").strip()
            a_val = actual.get(col, "").strip()
            
            # Custom matching logic
            match = False
            if col == "amount_safe_to_pay":
                try:
                    match = abs(float(e_val) - float(a_val)) < 0.02
                except:
                    match = (e_val == a_val)
            elif col == "spending_changes_needed":
                # Set match
                e_set = set(e_val.split("|")) if e_val and e_val != "none" else set()
                a_set = set(a_val.split("|")) if a_val and a_val != "none" else set()
                match = (e_set == a_set)
            else:
                match = (e_val == a_val)
                
            if match:
                metrics[col]["matches"] += 1
            else:
                # 5.4 Failure-case dump (abbreviated)
                pass # print(f"  {req.request_id} [{col}] Expected: '{e_val}' | Actual: '{a_val}'")

    print("\n--- Evaluation Results ---")
    print(f"{'Field':<35} | {'Matches':<7} | {'Total':<5} | {'Accuracy'}")
    print("-" * 65)
    for col, stats in metrics.items():
        m = stats["matches"]
        t = stats["total"]
        pct = (m / t * 100) if t > 0 else 0
        color = GREEN if pct == 100 else RED
        print(f"{color}{col:<35} | {m:<7} | {t:<5} | {pct:.1f}%{RESET}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="dataset")
    p.add_argument("--samples", default="dataset/sample_requests.csv")
    args = p.parse_args()
    
    evaluate(Path(args.dataset), Path(args.samples))
