#!/usr/bin/env python3
"""Regenerate the Chennai seed dataset (deterministic)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.data.seeds.generate_chennai import generate  # noqa: E402
import json  # noqa: E402

if __name__ == "__main__":
    out = ROOT / "backend" / "app" / "data" / "seeds" / "chennai_seed.json"
    data = generate()
    out.write_text(json.dumps(data, indent=1))
    print(f"regenerated {out} ({len(data['zones'])} zones, {len(data['sources'])} sources)")
