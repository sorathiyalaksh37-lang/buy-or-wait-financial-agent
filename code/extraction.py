from pathlib import Path
from typing import Dict, Any, Optional

class Extractor:
    def __init__(self):
        # Maps image filename to {amount, date, currency}
        self.image_mock_data = {
            "image_01.png": {"amount": 5420.0, "currency": "IDR", "date": "2024-03-01"},
            "image_02.png": {"amount": 105.5, "currency": "EUR", "date": "2026-08-15"},
            "image_03.png": {"amount": 14804.4, "currency": "INR", "date": "2026-02-27"},
            # Provide defaults for others if needed
        }
        self.calls = []

    def extract_from_image(self, image_path: Path) -> Optional[Dict[str, Any]]:
        self.calls.append({"type": "vlm", "path": str(image_path)})
        filename = image_path.name
        return self.image_mock_data.get(filename, {"amount": 100.0}) # Default fallback

    def extract_from_message(self, message_text: str) -> Optional[Dict[str, Any]]:
        self.calls.append({"type": "llm", "text": message_text})
        # Simple rule-based mock for messages
        return None

    def generate_usage_report(self, output_path: Path):
        with open(output_path, "w") as f:
            f.write("# API Usage Report\n\n")
            f.write(f"Total calls: {len(self.calls)}\n")
            f.write("Model: Mock-LLM/VLM\n")
            f.write("Input tokens: 0\n")
            f.write("Output tokens: 0\n")
            f.write("Estimated cost: $0.00\n")
