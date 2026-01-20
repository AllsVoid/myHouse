#!/usr/bin/env python3
"""
Generate rough polygon GeoJSON for each school based on LLM output.

Input: data/json/*.json
Output: data/polygons/*.geojson

Uses AMap Geocoding API (env AMAP_KEY).

Notes:
- This is an auto-draft polygon (bounding box of geocoded points).
- Intended for human correction later.
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen, Request

INPUT_DIR = Path("data/json")
OUTPUT_DIR = Path("data/polygons")
CACHE_FILE = Path("data/.geocode_cache.json")

DEFAULT_CITY = "苏州"
REQUEST_INTERVAL_SEC = 0.2


def load_cache() -> Dict[str, Tuple[float, float]]:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: Dict[str, Tuple[float, float]]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def geocode_amap(address: str, city: str, api_key: str, cache: Dict[str, Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    cache_key = f"{city}:{address}"
    if cache_key in cache:
        return tuple(cache[cache_key])

    params = {
        "key": api_key,
        "address": address,
        "city": city,
    }
    url = f"https://restapi.amap.com/v3/geocode/geo?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("status") != "1" or not data.get("geocodes"):
        return None

    location = data["geocodes"][0].get("location")
    if not location:
        return None

    lng_str, lat_str = location.split(",")
    lng, lat = float(lng_str), float(lat_str)
    cache[cache_key] = (lng, lat)
    return lng, lat


def bbox_polygon(points: List[Tuple[float, float]], buffer_deg: float = 0.002) -> Optional[List[List[float]]]:
    if not points:
        return None

    lngs = [p[0] for p in points]
    lats = [p[1] for p in points]
    min_lng, max_lng = min(lngs), max(lngs)
    min_lat, max_lat = min(lats), max(lats)

    # If only one point, create a small box around it
    if min_lng == max_lng and min_lat == max_lat:
        min_lng -= buffer_deg
        max_lng += buffer_deg
        min_lat -= buffer_deg
        max_lat += buffer_deg

    return [
        [min_lng, min_lat],
        [max_lng, min_lat],
        [max_lng, max_lat],
        [min_lng, max_lat],
        [min_lng, min_lat],
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate draft polygons from LLM JSON")
    parser.add_argument("--city", default=DEFAULT_CITY, help="Geocode city (default: 苏州)")
    parser.add_argument("--key", default=None, help="AMAP API key (or set AMAP_KEY env)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of files")
    parser.add_argument("--dry-run", action="store_true", help="Only show planned actions")
    args = parser.parse_args()

    api_key = args.key or os.getenv("AMAP_KEY")
    if not api_key:
        raise SystemExit("Missing AMAP_KEY. Provide --key or set AMAP_KEY env.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = load_cache()

    files = sorted(INPUT_DIR.glob("*.json"))
    if args.limit:
        files = files[: args.limit]

    if args.dry_run:
        print("[DRY-RUN] Files to process:")
        for f in files:
            print(f"  - {f.name}")
        return

    for file_path in files:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        schools = data.get("schools", [])

        features = []
        for school in schools:
            points: List[Tuple[float, float]] = []

            # Use boundaries and includes names as geocode input
            for b in school.get("boundaries", []):
                name = b.get("name")
                if name:
                    pt = geocode_amap(name, args.city, api_key, cache)
                    if pt:
                        points.append(pt)
                    time.sleep(REQUEST_INTERVAL_SEC)

            for inc in school.get("includes", []):
                name = inc.get("name")
                if name:
                    pt = geocode_amap(name, args.city, api_key, cache)
                    if pt:
                        points.append(pt)
                    time.sleep(REQUEST_INTERVAL_SEC)

            polygon = bbox_polygon(points)
            if not polygon:
                continue

            features.append({
                "type": "Feature",
                "properties": {
                    "school_name": school.get("school_name"),
                    "source_file": file_path.name,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [polygon],
                },
            })

        out_path = OUTPUT_DIR / file_path.with_suffix(".geojson").name
        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }
        out_path.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Generated: {out_path.name} (features: {len(features)})")

    # Update index.json
    index_path = OUTPUT_DIR / "index.json"
    geojson_files = sorted([p.name for p in OUTPUT_DIR.glob("*.geojson")])
    index_path.write_text(
        json.dumps(geojson_files, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Updated index.json (files: {len(geojson_files)})")

    save_cache(cache)


if __name__ == "__main__":
    main()
