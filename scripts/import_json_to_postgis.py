#!/usr/bin/env python3
"""
Import data/json/*.json into PostgreSQL (house database).

Usage:
  python scripts/import_json_to_postgis.py \
    --dsn "postgresql://crushark:psql%40WKY_0220@localhost:5432/house"

Environment:
  DATABASE_URL (optional)
"""

import argparse
import json
from pathlib import Path
from typing import Optional

try:
    import psycopg
except Exception as e:
    raise SystemExit(
        "Missing dependency: psycopg. Install with `pip install psycopg`"
    )

DATA_DIR = Path("data/json")


def parse_year_from_filename(name: str) -> Optional[int]:
    for year in range(2020, 2036):
        if str(year) in name:
            return year
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Import data/json into PostGIS")
    parser.add_argument(
        "--dsn",
        default=None,
        help="PostgreSQL DSN (or set DATABASE_URL env var)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of files to import",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported, without DB writes",
    )
    args = parser.parse_args()

    dsn = args.dsn
    if not dsn:
        import os

        dsn = os.getenv("DATABASE_URL")

    if not dsn:
        raise SystemExit("Missing DSN. Use --dsn or set DATABASE_URL.")

    files = sorted(DATA_DIR.glob("*.json"))
    if args.limit:
        files = files[: args.limit]

    if not files:
        print(f"No JSON files found in {DATA_DIR}")
        return

    if args.dry_run:
        print("[DRY-RUN] Files to import:")
        for f in files:
            print(f"  - {f.name}")
        return

    with psycopg.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            for file_path in files:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                schools = data.get("schools", [])
                year = parse_year_from_filename(file_path.name)

                for school in schools:
                    school_name = school.get("school_name")
                    if not school_name:
                        continue

                    # upsert school
                    cur.execute(
                        """
                        INSERT INTO schools (name)
                        VALUES (%s)
                        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                        RETURNING id
                        """,
                        (school_name,),
                    )
                    school_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        INSERT INTO catchment_zones
                            (school_id, year, source_file, raw_json, boundaries, includes)
                        VALUES
                            (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            school_id,
                            year,
                            file_path.name,
                            json.dumps(school, ensure_ascii=False),
                            json.dumps(school.get("boundaries", []), ensure_ascii=False),
                            json.dumps(school.get("includes", []), ensure_ascii=False),
                        ),
                    )

                print(f"Imported: {file_path.name} (schools: {len(schools)})")


if __name__ == "__main__":
    main()
