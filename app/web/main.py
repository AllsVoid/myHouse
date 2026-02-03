"""FastAPI web app for GeoJSON viewer."""

import json
import os
import sys
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

try:
    from psycopg import connect
    from psycopg.types.json import Json
except Exception as exc:  # pragma: no cover - runtime dependency check
    connect = None
    Json = None
    _PSYCOPG_IMPORT_ERROR = exc
else:
    _PSYCOPG_IMPORT_ERROR = None


def _get_base_dir() -> Path:
    override = os.getenv("HOUSE_BASE_DIR")
    if override:
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        return Path.cwd()
    return Path(__file__).resolve().parents[2]


BASE_DIR = _get_base_dir()
RESOURCE_BASE = Path(getattr(sys, "_MEIPASS", BASE_DIR))
load_dotenv(dotenv_path=BASE_DIR / ".env")
POLYGON_DIR = BASE_DIR / "data" / "polygons"
POINTS_DIR = POLYGON_DIR / "points"
ITEMS_DIR = POLYGON_DIR / "items"
BACKUP_DIR = POLYGON_DIR / "_backup"
AMAP_KEY = os.getenv("AMAP_KEY", "").strip()
AMAP_JS_KEY = os.getenv("AMAP_JS_KEY", "").strip()
AMAP_SECURITY_JS_CODE = os.getenv("AMAP_SECURITY_JS_CODE", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
API_BASE_URL = os.getenv("API_BASE_URL", "").strip()
FRONTEND_ORIGINS = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).strip()

app = FastAPI(title="GeoJSON API")

allowed_origins = [
    origin.strip() for origin in FRONTEND_ORIGINS.split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=RESOURCE_BASE / "app" / "web" / "static"),
    name="static",
)
templates = Jinja2Templates(directory=str(RESOURCE_BASE / "app" / "web" / "templates"))
FRONTEND_DIST_DIR = RESOURCE_BASE / "frontend" / "dist"


if FRONTEND_DIST_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST_DIR / "assets"),
        name="frontend-assets",
    )

    @app.get("/{path:path}", include_in_schema=False)
    def serve_frontend(path: str):
        if path.startswith("api/") or path.startswith("static/"):
            raise HTTPException(status_code=404, detail="Not found")
        target = FRONTEND_DIST_DIR / path
        if path and target.exists() and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(FRONTEND_DIST_DIR / "index.html"))

else:

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/geo", response_class=HTMLResponse)
    def geo_page(request: Request):
        return templates.TemplateResponse(
            "geo.html",
            {
                "request": request,
                "amap_key": AMAP_JS_KEY,
                "amap_security_js_code": AMAP_SECURITY_JS_CODE,
            },
        )

    @app.get("/houses", response_class=HTMLResponse)
    def houses_page(request: Request):
        return templates.TemplateResponse("houses.html", {"request": request})


def _validate_filename(filename: str) -> None:
    if not filename or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")


def _write_geojson_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup_path = (
            BACKUP_DIR / f"{path.stem}.{int(path.stat().st_mtime)}{path.suffix}"
        )
        if not backup_path.exists():
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")


def _get_file_cache_headers(path: Path) -> tuple[str, datetime, dict]:
    stat = path.stat()
    etag = f'W/"{stat.st_mtime_ns}-{stat.st_size}"'
    last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    headers = {
        "ETag": etag,
        "Last-Modified": format_datetime(last_modified, usegmt=True),
        "Cache-Control": "public, max-age=86400",
    }
    return etag, last_modified, headers


def _get_dir_cache_headers(
    dir_path: Path, pattern: str = "*.geojson"
) -> tuple[str, datetime, dict]:
    latest_mtime_ns = 0
    file_count = 0
    for path in dir_path.glob(pattern):
        if not path.is_file():
            continue
        file_count += 1
        mtime_ns = path.stat().st_mtime_ns
        if mtime_ns > latest_mtime_ns:
            latest_mtime_ns = mtime_ns
    if latest_mtime_ns == 0:
        last_modified = datetime.fromtimestamp(0, tz=timezone.utc)
    else:
        last_modified = datetime.fromtimestamp(latest_mtime_ns / 1e9, tz=timezone.utc)
    etag = f'W/"{latest_mtime_ns}-{file_count}"'
    headers = {
        "ETag": etag,
        "Last-Modified": format_datetime(last_modified, usegmt=True),
        "Cache-Control": "public, max-age=86400",
    }
    return etag, last_modified, headers


def _is_not_modified(request: Request, etag: str, last_modified: datetime) -> bool:
    inm = request.headers.get("if-none-match")
    if inm and inm == etag:
        return True
    ims = request.headers.get("if-modified-since")
    if ims:
        try:
            ims_dt = parsedate_to_datetime(ims)
            if ims_dt.tzinfo is None:
                ims_dt = ims_dt.replace(tzinfo=timezone.utc)
            if last_modified <= ims_dt:
                return True
        except Exception:
            return False
    return False


def _ensure_geojson_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS geojson_store (
                id BIGSERIAL PRIMARY KEY,
                file_name TEXT NOT NULL,
                school_name TEXT,
                kind TEXT NOT NULL,
                geojson JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS geojson_store_unique
            ON geojson_store (file_name, kind, school_name);
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS geojson_history (
                id BIGSERIAL PRIMARY KEY,
                save_id UUID NOT NULL,
                file_name TEXT NOT NULL,
                school_name TEXT,
                kind TEXT NOT NULL,
                geojson JSONB NOT NULL,
                saved_at TIMESTAMPTZ NOT NULL
            );
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS geojson_history_idx
            ON geojson_history (file_name, school_name, saved_at DESC);
            """
        )


def _ensure_house_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS house_data (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                area NUMERIC,
                price NUMERIC,
                longitude NUMERIC,
                latitude NUMERIC,
                geo_address TEXT,
                layout TEXT,
                building TEXT,
                floor TEXT,
                elevator TEXT,
                age TEXT,
                ownership TEXT,
                usage TEXT,
                house_status TEXT,
                intention TEXT,
                house_code TEXT,
                link TEXT,
                layout_image_data TEXT,
                layout_image_type TEXT,
                layout_images JSONB,
                note TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS house_data_created_at_idx
            ON house_data (created_at DESC);
            """
        )
        cur.execute("ALTER TABLE house_data ADD COLUMN IF NOT EXISTS price NUMERIC;")
        cur.execute(
            "ALTER TABLE house_data ADD COLUMN IF NOT EXISTS longitude NUMERIC;"
        )
        cur.execute("ALTER TABLE house_data ADD COLUMN IF NOT EXISTS latitude NUMERIC;")
        cur.execute("ALTER TABLE house_data ADD COLUMN IF NOT EXISTS geo_address TEXT;")
        cur.execute(
            "ALTER TABLE house_data ADD COLUMN IF NOT EXISTS layout_images JSONB;"
        )
        cur.execute(
            "ALTER TABLE house_data ADD COLUMN IF NOT EXISTS house_status TEXT;"
        )
        cur.execute("ALTER TABLE house_data ADD COLUMN IF NOT EXISTS intention TEXT;")


def _ensure_house_geo_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS house_geo (
                id SMALLINT PRIMARY KEY,
                geojson JSONB NOT NULL,
                etag TEXT,
                last_modified TIMESTAMPTZ,
                source_updated_at TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )


def _house_has_columns(conn, column_names: list[str]) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'house_data';
            """
        )
        existing = {row[0] for row in cur.fetchall()}
    return all(name in existing for name in column_names)


def _safe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _geocode_address(
    address: str,
) -> tuple[Optional[float], Optional[float], Optional[str]]:
    if not address or not AMAP_KEY:
        return None, None, None
    from urllib.parse import urlencode
    from urllib.request import urlopen

    params = urlencode({"key": AMAP_KEY, "address": address})
    url = f"https://restapi.amap.com/v3/geocode/geo?{params}"
    try:
        with urlopen(url, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None, None, None
    geocodes = payload.get("geocodes") or []
    if not geocodes:
        return None, None, None
    location = geocodes[0].get("location")
    if not location or "," not in location:
        return None, None, None
    lng_str, lat_str = location.split(",", 1)
    try:
        return float(lng_str), float(lat_str), address
    except ValueError:
        return None, None, None


@app.get("/api/config")
def get_frontend_config():
    return {
        "api_base_url": API_BASE_URL,
        "amap_key": AMAP_KEY,
        "amap_js_key": AMAP_JS_KEY,
        "amap_security_js_code": AMAP_SECURITY_JS_CODE,
    }


@app.get("/api/houses")
def list_houses():
    if not DATABASE_URL:
        raise HTTPException(status_code=400, detail="Missing DATABASE_URL")
    if not connect:
        raise HTTPException(
            status_code=500,
            detail=(
                "psycopg is not available. Install psycopg with a libpq backend "
                "(e.g. `uv add 'psycopg[binary]'` or install system libpq)."
            ),
        )
    try:
        with connect(DATABASE_URL) as conn:
            _ensure_house_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id, name, address, area, price, longitude, latitude, geo_address,
                        layout, building, floor, elevator, age,
                        ownership, usage, house_status, intention, house_code, link, layout_image_data, layout_image_type,
                        layout_images, note, created_at, updated_at
                    FROM house_data
                    ORDER BY created_at DESC;
                    """
                )
                rows = cur.fetchall()
        result = []
        for row in rows:
            result.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "address": row[2],
                    "area": float(row[3]) if row[3] is not None else None,
                    "price": float(row[4]) if row[4] is not None else None,
                    "longitude": float(row[5]) if row[5] is not None else None,
                    "latitude": float(row[6]) if row[6] is not None else None,
                    "geoAddress": row[7],
                    "layout": row[8],
                    "building": row[9],
                    "floor": row[10],
                    "elevator": row[11],
                    "age": row[12],
                    "ownership": row[13],
                    "usage": row[14],
                    "houseStatus": row[15],
                    "intention": row[16],
                    "houseCode": row[17],
                    "link": row[18],
                    "layoutImageData": row[19],
                    "layoutImageType": row[20],
                    "layoutImages": row[21],
                    "note": row[22],
                    "createdAt": row[23].isoformat() if row[23] else None,
                    "updatedAt": row[24].isoformat() if row[24] else None,
                }
            )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/houses")
async def create_house(request: Request):
    if not DATABASE_URL:
        raise HTTPException(status_code=400, detail="Missing DATABASE_URL")
    if not connect:
        raise HTTPException(
            status_code=500,
            detail=(
                "psycopg is not available. Install psycopg with a libpq backend "
                "(e.g. `uv add 'psycopg[binary]'` or install system libpq)."
            ),
        )
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    name = (data.get("name") or "").strip()
    address = (data.get("address") or "").strip()
    area = data.get("area")
    price = data.get("price")
    building = (data.get("building") or "").strip()
    if (
        not name
        or not address
        or area is None
        or str(area).strip() == ""
        or price is None
        or str(price).strip() == ""
    ):
        raise HTTPException(status_code=400, detail="Missing required fields")
    geo_query = f"{address} {building}".strip()
    longitude, latitude, geo_address = _geocode_address(geo_query)
    layout_images = data.get("layoutImages")
    if not layout_images and data.get("layoutImageData"):
        layout_images = [data.get("layoutImageData")]
    try:
        with connect(DATABASE_URL) as conn:
            _ensure_house_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO house_data (
                        name, address, area, price, longitude, latitude, geo_address,
                        layout, building, floor, elevator, age,
                        ownership, usage, house_status, intention, house_code, link, layout_image_data, layout_image_type, layout_images, note
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING
                        id, name, address, area, price, longitude, latitude, geo_address,
                        layout, building, floor, elevator, age,
                        ownership, usage, house_status, intention, house_code, link, layout_image_data, layout_image_type,
                        layout_images, note, created_at, updated_at;
                    """,
                    (
                        name,
                        address,
                        area,
                        price,
                        longitude,
                        latitude,
                        geo_address,
                        data.get("layout"),
                        building,
                        data.get("floor"),
                        data.get("elevator"),
                        data.get("age"),
                        data.get("ownership"),
                        data.get("usage"),
                        data.get("houseStatus"),
                        data.get("intention"),
                        data.get("houseCode"),
                        data.get("link"),
                        data.get("layoutImageData"),
                        data.get("layoutImageType"),
                        (
                            Json(layout_images)
                            if Json and layout_images is not None
                            else layout_images
                        ),
                        data.get("note"),
                    ),
                )
                row = cur.fetchone()
        return {
            "id": row[0],
            "name": row[1],
            "address": row[2],
            "area": float(row[3]) if row[3] is not None else None,
            "price": float(row[4]) if row[4] is not None else None,
            "longitude": float(row[5]) if row[5] is not None else None,
            "latitude": float(row[6]) if row[6] is not None else None,
            "geoAddress": row[7],
            "layout": row[8],
            "building": row[9],
            "floor": row[10],
            "elevator": row[11],
            "age": row[12],
            "ownership": row[13],
            "usage": row[14],
            "houseStatus": row[15],
            "intention": row[16],
            "houseCode": row[17],
            "link": row[18],
            "layoutImageData": row[19],
            "layoutImageType": row[20],
            "layoutImages": row[21],
            "note": row[22],
            "createdAt": row[23].isoformat() if row[23] else None,
            "updatedAt": row[24].isoformat() if row[24] else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/api/houses/{house_id}")
async def update_house(house_id: int, request: Request):
    if not DATABASE_URL:
        raise HTTPException(status_code=400, detail="Missing DATABASE_URL")
    if not connect:
        raise HTTPException(
            status_code=500,
            detail=(
                "psycopg is not available. Install psycopg with a libpq backend "
                "(e.g. `uv add 'psycopg[binary]'` or install system libpq)."
            ),
        )
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    name = (data.get("name") or "").strip()
    address = (data.get("address") or "").strip()
    area = data.get("area")
    price = data.get("price")
    building = (data.get("building") or "").strip()
    if (
        not name
        or not address
        or area is None
        or str(area).strip() == ""
        or price is None
        or str(price).strip() == ""
    ):
        raise HTTPException(status_code=400, detail="Missing required fields")
    geo_query = f"{address} {building}".strip()
    longitude, latitude, geo_address = _geocode_address(geo_query)
    layout_images = data.get("layoutImages")
    if not layout_images and data.get("layoutImageData"):
        layout_images = [data.get("layoutImageData")]
    try:
        with connect(DATABASE_URL) as conn:
            _ensure_house_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE house_data
                    SET
                        name = %s,
                        address = %s,
                        area = %s,
                        price = %s,
                        longitude = %s,
                        latitude = %s,
                        geo_address = %s,
                        layout = %s,
                        building = %s,
                        floor = %s,
                        elevator = %s,
                        age = %s,
                        ownership = %s,
                        usage = %s,
                        house_status = %s,
                        intention = %s,
                        house_code = %s,
                        link = %s,
                        layout_image_data = %s,
                        layout_image_type = %s,
                        layout_images = %s,
                        note = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING
                        id, name, address, area, price, longitude, latitude, geo_address,
                        layout, building, floor, elevator, age,
                        ownership, usage, house_status, intention, house_code, link, layout_image_data, layout_image_type,
                        layout_images, note, created_at, updated_at;
                    """,
                    (
                        name,
                        address,
                        area,
                        price,
                        longitude,
                        latitude,
                        geo_address,
                        data.get("layout"),
                        building,
                        data.get("floor"),
                        data.get("elevator"),
                        data.get("age"),
                        data.get("ownership"),
                        data.get("usage"),
                        data.get("houseStatus"),
                        data.get("intention"),
                        data.get("houseCode"),
                        data.get("link"),
                        data.get("layoutImageData"),
                        data.get("layoutImageType"),
                        (
                            Json(layout_images)
                            if Json and layout_images is not None
                            else layout_images
                        ),
                        data.get("note"),
                        house_id,
                    ),
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="House not found")
        return {
            "id": row[0],
            "name": row[1],
            "address": row[2],
            "area": float(row[3]) if row[3] is not None else None,
            "price": float(row[4]) if row[4] is not None else None,
            "longitude": float(row[5]) if row[5] is not None else None,
            "latitude": float(row[6]) if row[6] is not None else None,
            "geoAddress": row[7],
            "layout": row[8],
            "building": row[9],
            "floor": row[10],
            "elevator": row[11],
            "age": row[12],
            "ownership": row[13],
            "usage": row[14],
            "houseStatus": row[15],
            "intention": row[16],
            "houseCode": row[17],
            "link": row[18],
            "layoutImageData": row[19],
            "layoutImageType": row[20],
            "layoutImages": row[21],
            "note": row[22],
            "createdAt": row[23].isoformat() if row[23] else None,
            "updatedAt": row[24].isoformat() if row[24] else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/houses/{house_id}")
def delete_house(house_id: int):
    if not DATABASE_URL:
        raise HTTPException(status_code=400, detail="Missing DATABASE_URL")
    if not connect:
        raise HTTPException(
            status_code=500,
            detail=(
                "psycopg is not available. Install psycopg with a libpq backend "
                "(e.g. `uv add 'psycopg[binary]'` or install system libpq)."
            ),
        )
    try:
        with connect(DATABASE_URL) as conn:
            _ensure_house_table(conn)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM house_data WHERE id = %s;", (house_id,))
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/houses/geojson")
def get_houses_geojson(request: Request):
    if not DATABASE_URL:
        raise HTTPException(status_code=400, detail="Missing DATABASE_URL")
    if not connect:
        raise HTTPException(
            status_code=500,
            detail=(
                "psycopg is not available. Install psycopg with a libpq backend "
                "(e.g. `uv add 'psycopg[binary]'` or install system libpq)."
            ),
        )
    try:
        with connect(DATABASE_URL) as conn:
            _ensure_house_table(conn)
            _ensure_house_geo_table(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(updated_at) FROM house_data;")
                source_updated_at = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT geojson, etag, last_modified, source_updated_at
                    FROM house_geo
                    WHERE id = 1;
                    """
                )
                cached = cur.fetchone()

            if cached and cached[3] == source_updated_at:
                return Response(
                    content=json.dumps(cached[0], ensure_ascii=False),
                    media_type="application/json",
                )

            if not _house_has_columns(conn, ["longitude", "latitude"]):
                payload = {"type": "FeatureCollection", "features": []}
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            id, name, address, price, layout, building, floor, area,
                            longitude, latitude, house_code, usage, house_status, intention
                        FROM house_data
                        WHERE longitude IS NOT NULL AND latitude IS NOT NULL
                        ORDER BY created_at DESC;
                        """
                    )
                    rows = cur.fetchall()
                features = []
                for row in rows:
                    lng = _safe_float(row[8])
                    lat = _safe_float(row[9])
                    if lng is None or lat is None:
                        continue
                    features.append(
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [lng, lat],
                            },
                            "properties": {
                                "id": row[0],
                                "name": row[1],
                                "address": row[2],
                                "price": _safe_float(row[3]),
                                "layout": row[4],
                                "building": row[5],
                                "floor": row[6],
                                "area": _safe_float(row[7]),
                                "houseCode": row[10],
                                "usage": row[11],
                                "houseStatus": row[12],
                                "intention": row[13],
                            },
                        }
                    )
                payload = {"type": "FeatureCollection", "features": features}

            with conn.cursor() as cur:
                geojson_value = (
                    Json(payload) if Json else json.dumps(payload, ensure_ascii=False)
                )
                cur.execute(
                    """
                    INSERT INTO house_geo (id, geojson, etag, last_modified, source_updated_at, updated_at)
                    VALUES (1, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET geojson = EXCLUDED.geojson,
                        etag = EXCLUDED.etag,
                        last_modified = EXCLUDED.last_modified,
                        source_updated_at = EXCLUDED.source_updated_at,
                        updated_at = NOW();
                    """,
                    (geojson_value, None, None, source_updated_at),
                )

        return Response(
            content=json.dumps(payload, ensure_ascii=False),
            media_type="application/json",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/polygons", response_model=List[str])
def list_polygons(request: Request) -> List[str]:
    if not POLYGON_DIR.exists():
        return []
    etag, last_modified, headers = _get_dir_cache_headers(POLYGON_DIR)
    if _is_not_modified(request, etag, last_modified):
        return Response(status_code=304, headers=headers)
    response = sorted([p.name for p in POLYGON_DIR.glob("*.geojson")])
    return Response(
        content=json.dumps(response, ensure_ascii=False),
        media_type="application/json",
        headers=headers,
    )


@app.get("/api/polygons/{filename}")
def get_polygon(request: Request, filename: str):
    _validate_filename(filename)
    path = POLYGON_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    etag, last_modified, headers = _get_file_cache_headers(path)
    if _is_not_modified(request, etag, last_modified):
        return Response(status_code=304, headers=headers)
    return FileResponse(str(path), media_type="application/json", headers=headers)


@app.post("/api/polygons/{filename}")
async def save_polygon(filename: str, request: Request):
    _validate_filename(filename)
    path = POLYGON_DIR / filename
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid GeoJSON payload")
    _write_geojson_file(path, data)
    return {"status": "ok", "file": filename}


@app.post("/api/save_current")
async def save_current(request: Request):
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    file_name = data.get("file_name")
    school_name = data.get("school_name") or None
    polygons = data.get("polygons")
    points = data.get("points")
    if not file_name:
        raise HTTPException(status_code=400, detail="Missing file_name")
    if not DATABASE_URL:
        raise HTTPException(status_code=400, detail="Missing DATABASE_URL")
    if not connect or not Json:
        raise HTTPException(
            status_code=500,
            detail=(
                "psycopg is not available. Install psycopg with a libpq backend "
                "(e.g. `uv add 'psycopg[binary]'` or install system libpq)."
            ),
        )
    if not polygons and not points:
        raise HTTPException(status_code=400, detail="No data to save")

    try:
        save_id = data.get("save_id")
        if not save_id:
            from uuid import uuid4

            save_id = uuid4()
        saved_at = datetime.now(timezone.utc)
        with connect(DATABASE_URL) as conn:
            _ensure_geojson_table(conn)
            with conn.cursor() as cur:
                if polygons:
                    cur.execute(
                        """
                        INSERT INTO geojson_store (file_name, school_name, kind, geojson)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (file_name, kind, school_name)
                        DO UPDATE SET geojson = EXCLUDED.geojson, updated_at = NOW();
                        """,
                        (file_name, school_name, "polygons", Json(polygons)),
                    )
                    cur.execute(
                        """
                        INSERT INTO geojson_history
                            (save_id, file_name, school_name, kind, geojson, saved_at)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (
                            save_id,
                            file_name,
                            school_name,
                            "polygons",
                            Json(polygons),
                            saved_at,
                        ),
                    )
                if points:
                    cur.execute(
                        """
                        INSERT INTO geojson_store (file_name, school_name, kind, geojson)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (file_name, kind, school_name)
                        DO UPDATE SET geojson = EXCLUDED.geojson, updated_at = NOW();
                        """,
                        (file_name, school_name, "points", Json(points)),
                    )
                    cur.execute(
                        """
                        INSERT INTO geojson_history
                            (save_id, file_name, school_name, kind, geojson, saved_at)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (
                            save_id,
                            file_name,
                            school_name,
                            "points",
                            Json(points),
                            saved_at,
                        ),
                    )
        return {
            "status": "ok",
            "file": file_name,
            "save_id": str(save_id),
            "saved_at": saved_at.isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/save_all")
async def save_all():
    if not DATABASE_URL:
        raise HTTPException(status_code=400, detail="Missing DATABASE_URL")
    if not connect or not Json:
        raise HTTPException(
            status_code=500,
            detail=(
                "psycopg is not available. Install psycopg with a libpq backend "
                "(e.g. `uv add 'psycopg[binary]'` or install system libpq)."
            ),
        )
    if not POLYGON_DIR.exists():
        raise HTTPException(status_code=404, detail="Polygon directory not found")

    from uuid import uuid4

    save_id = uuid4()
    saved_at = datetime.now(timezone.utc)
    errors = []
    polygon_saved = 0
    points_saved = 0

    try:
        with connect(DATABASE_URL) as conn:
            _ensure_geojson_table(conn)
            with conn.cursor() as cur:
                for polygon_path in sorted(POLYGON_DIR.glob("*.geojson")):
                    file_name = polygon_path.name
                    try:
                        polygons = json.loads(polygon_path.read_text(encoding="utf-8"))
                    except Exception as exc:
                        errors.append(f"{file_name}: polygons load failed ({exc})")
                        continue

                    cur.execute(
                        """
                        INSERT INTO geojson_store (file_name, school_name, kind, geojson)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (file_name, kind, school_name)
                        DO UPDATE SET geojson = EXCLUDED.geojson, updated_at = NOW();
                        """,
                        (file_name, None, "polygons", Json(polygons)),
                    )
                    cur.execute(
                        """
                        INSERT INTO geojson_history
                            (save_id, file_name, school_name, kind, geojson, saved_at)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (
                            save_id,
                            file_name,
                            None,
                            "polygons",
                            Json(polygons),
                            saved_at,
                        ),
                    )
                    polygon_saved += 1

                    points_path = POINTS_DIR / f"{polygon_path.stem}.points.geojson"
                    if points_path.exists():
                        try:
                            points = json.loads(points_path.read_text(encoding="utf-8"))
                        except Exception as exc:
                            errors.append(
                                f"{points_path.name}: points load failed ({exc})"
                            )
                        else:
                            cur.execute(
                                """
                                INSERT INTO geojson_store (file_name, school_name, kind, geojson)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (file_name, kind, school_name)
                                DO UPDATE SET geojson = EXCLUDED.geojson, updated_at = NOW();
                                """,
                                (file_name, None, "points", Json(points)),
                            )
                            cur.execute(
                                """
                                INSERT INTO geojson_history
                                    (save_id, file_name, school_name, kind, geojson, saved_at)
                                VALUES (%s, %s, %s, %s, %s, %s);
                                """,
                                (
                                    save_id,
                                    file_name,
                                    None,
                                    "points",
                                    Json(points),
                                    saved_at,
                                ),
                            )
                            points_saved += 1

        return {
            "status": "ok",
            "save_id": str(save_id),
            "saved_at": saved_at.isoformat(),
            "polygons_saved": polygon_saved,
            "points_saved": points_saved,
            "errors": errors,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/history")
def list_history(
    file_name: str = Query(..., min_length=1),
    school_name: Optional[str] = None,
):
    if not DATABASE_URL:
        raise HTTPException(status_code=400, detail="Missing DATABASE_URL")
    if not connect or not Json:
        raise HTTPException(
            status_code=500,
            detail=(
                "psycopg is not available. Install psycopg with a libpq backend "
                "(e.g. `uv add 'psycopg[binary]'` or install system libpq)."
            ),
        )
    try:
        with connect(DATABASE_URL) as conn:
            _ensure_geojson_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT save_id, saved_at
                    FROM geojson_history
                    WHERE file_name = %s AND school_name IS NOT DISTINCT FROM %s
                    GROUP BY save_id, saved_at
                    ORDER BY saved_at DESC;
                    """,
                    (file_name, school_name),
                )
                rows = cur.fetchall()
        return [{"save_id": str(r[0]), "saved_at": r[1].isoformat()} for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/history/{save_id}")
def get_history(save_id: str):
    if not DATABASE_URL:
        raise HTTPException(status_code=400, detail="Missing DATABASE_URL")
    if not connect or not Json:
        raise HTTPException(
            status_code=500,
            detail=(
                "psycopg is not available. Install psycopg with a libpq backend "
                "(e.g. `uv add 'psycopg[binary]'` or install system libpq)."
            ),
        )
    try:
        with connect(DATABASE_URL) as conn:
            _ensure_geojson_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT file_name, school_name, kind, geojson, saved_at
                    FROM geojson_history
                    WHERE save_id = %s;
                    """,
                    (save_id,),
                )
                rows = cur.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="History not found")
        payload = {"polygons": None, "points": None}
        file_name = rows[0][0]
        school_name = rows[0][1]
        saved_at = rows[0][4]
        for row in rows:
            kind = row[2]
            if kind == "polygons":
                payload["polygons"] = row[3]
            elif kind == "points":
                payload["points"] = row[3]
        payload.update(
            {
                "file_name": file_name,
                "school_name": school_name,
                "saved_at": saved_at.isoformat() if saved_at else None,
            }
        )
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/points/{filename}")
def get_points(request: Request, filename: str):
    _validate_filename(filename)
    if filename.endswith(".geojson"):
        points_name = filename[: -len(".geojson")] + ".points.geojson"
    else:
        points_name = filename + ".points.geojson"
    path = POINTS_DIR / points_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    etag, last_modified, headers = _get_file_cache_headers(path)
    if _is_not_modified(request, etag, last_modified):
        return Response(status_code=304, headers=headers)
    return FileResponse(str(path), media_type="application/json", headers=headers)


@app.post("/api/points/{filename}")
async def save_points(filename: str, request: Request):
    _validate_filename(filename)
    if filename.endswith(".geojson"):
        points_name = filename[: -len(".geojson")] + ".points.geojson"
    else:
        points_name = filename + ".points.geojson"
    path = POINTS_DIR / points_name
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid GeoJSON payload")
    _write_geojson_file(path, data)
    return {"status": "ok", "file": points_name}


@app.get("/api/items/{filename}")
def get_items(request: Request, filename: str):
    _validate_filename(filename)
    if filename.endswith(".geojson"):
        items_name = filename[: -len(".geojson")] + ".items.geojson"
    else:
        items_name = filename + ".items.geojson"
    path = ITEMS_DIR / items_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    etag, last_modified, headers = _get_file_cache_headers(path)
    if _is_not_modified(request, etag, last_modified):
        return Response(status_code=304, headers=headers)
    return FileResponse(str(path), media_type="application/json", headers=headers)
