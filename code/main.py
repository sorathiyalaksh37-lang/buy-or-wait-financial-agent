"""
main.py — Phase 0.10: Single command entry point.
Reads dataset/, processes all requests, writes output.csv, and validates it.
"""

from __future__ import annotations
import csv
import sys
from pathlib import Path

from ingestion import load_dataset
from decision import DecisionEngine
from schema import OUTPUT_COLUMNS
from validator import validate_output_csv
from extraction import Extractor

def main():
    # Seed RNG if any random choice is used later for determinism
    import random
    random.seed(42)

    dataset_root = Path("dataset")
    if not dataset_root.exists():
        print(f"Error: {dataset_root} not found.")
        sys.exit(1)
        
    output_file = Path("output.csv")
    
    # Initialize Extractor
    extractor = Extractor()
    
    # 1. Load Dataset
    dataset = load_dataset(dataset_root, extractor)
    
    # 2. Initialize Decision Engine
    engine = DecisionEngine(dataset)
    
    # 3. Process Requests
    print(f"Processing {len(dataset.requests)} requests...")
    results = []
    
    for i, req in enumerate(dataset.requests):
        if i > 0 and i % 50 == 0:
            print(f"  Processed {i}/{len(dataset.requests)}...")
            
        try:
            row = engine.process_request(req)
            results.append(row)
        except Exception as e:
            print(f"Error processing {req.request_id}: {e}")
            # Fallback
            from schema import OutputRow
            results.append(OutputRow(request_id=req.request_id))

    # 4. Write output.csv
    print(f"Writing {len(results)} rows to {output_file}...")
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_dict())
            
    # 5. Validate
    print("Validating output...")
    requests_file = dataset_root / "requests.csv"
    is_valid = validate_output_csv(output_file, requests_file, dataset_root)
    
    if is_valid:
        print("Success! output.csv is ready.")
        Path("evaluation").mkdir(exist_ok=True)
        extractor.generate_usage_report(Path("evaluation/usage_report.md"))
        sys.exit(0)
    else:
        print("Validation failed. See errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
