#!/usr/bin/env python3
"""Update data/polygons/index.json from *.geojson files."""
import json
from pathlib import Path

path = Path("data/polygons")
files = sorted([p.name for p in path.glob("*.geojson")])
path.joinpath("index.json").write_text(
    json.dumps(files, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"Wrote index.json with {len(files)} files")
