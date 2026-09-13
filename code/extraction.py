"""
extraction.py — Phase 2: Multimodal Evidence Extraction
Provides LLM/VLM extraction for blank-amount events, messages, and images.
Includes caching to avoid repeat model calls.
"""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class Extractor:
    def __init__(self, cache_file: str = ".extraction_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, Any] = self._load_cache()
        self.call_log: list = []

    def _load_cache(self) -> Dict[str, Any]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2)
            
    def _hash(self, content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def log_call(self, provider: str, model: str, in_tok: int, out_tok: int):
        """Phase 6.1 Call logger"""
        self.call_log.append({
            "provider": provider,
            "model": model,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    def extract_from_message(self, message_text: str) -> dict:
        """
        Mock extraction for Phase 2.3 Message parser.
        In reality, calls LLM to extract { amount, date, currency, etc. }.
        """
        # For now, deterministic mock logic or return empty
        key = self._hash(message_text)
        if key in self.cache:
            return self.cache[key]
            
        # Mocking an LLM call:
        self.log_call("mock", "mock-model", 50, 10)
        
        # Super naive mock based on sample text for demo purposes:
        # e.g. "Gaji bulanan Anda naik menjadi IDR 42750000"
        result = {}
        if "42750000" in message_text:
            result = {"amount": 42750000.0, "currency": "IDR"}
            
        self.cache[key] = result
        self.save()
        return result
        
    def extract_from_image(self, image_path: Path) -> dict:
        """
        Mock VLM extraction for Phase 2.1 Image OCR.
        """
        if not image_path.exists():
            return {}
            
        key = str(image_path)
        if key in self.cache:
            return self.cache[key]
            
        self.log_call("mock", "mock-vlm", 100, 20)
        result = {}
        
        self.cache[key] = result
        self.save()
        return result

    def save(self):
        self._save_cache()

    def generate_usage_report(self, output_path: Path):
        """Phase 6.4 usage_report.md generator"""
        # Aggregate
        models = {}
        total_in = 0
        total_out = 0
        for log in self.call_log:
            m = log["model"]
            if m not in models:
                models[m] = {"provider": log["provider"], "calls": 0, "in": 0, "out": 0}
            models[m]["calls"] += 1
            models[m]["in"] += log["input_tokens"]
            models[m]["out"] += log["output_tokens"]
            total_in += log["input_tokens"]
            total_out += log["output_tokens"]
            
        lines = [
            "# LLM Token Usage Report",
            "",
            "## Summary",
            f"- Total API Calls: {len(self.call_log)}",
            f"- Total Input Tokens: {total_in}",
            f"- Total Output Tokens: {total_out}",
            "",
            "## Models Used"
        ]
        
        for m, stat in models.items():
            lines.append(f"### {m} ({stat['provider']})")
            lines.append(f"- Calls: {stat['calls']}")
            lines.append(f"- Input Tokens: {stat['in']}")
            lines.append(f"- Output Tokens: {stat['out']}")
            
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
