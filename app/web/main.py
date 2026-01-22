"""FastAPI web app for GeoJSON viewer."""

import json
import os
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

BASE_DIR = Path(__file__).resolve().parents[2]
POLYGON_DIR = BASE_DIR / "data" / "polygons"
POINTS_DIR = POLYGON_DIR / "points"
ITEMS_DIR = POLYGON_DIR / "items"
BACKUP_DIR = POLYGON_DIR / "_backup"
AMAP_JS_KEY = os.getenv("AMAP_JS_KEY", "").strip()
AMAP_SECURITY_JS_CODE = os.getenv("AMAP_SECURITY_JS_CODE", "").strip()

app = FastAPI(title="GeoJSON Viewer")

# Static files
app.mount(
    "/static", StaticFiles(directory=BASE_DIR / "app" / "web" / "static"), name="static"
)

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "web" / "templates"))


def _validate_filename(filename: str) -> None:
    if not filename or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")


def _write_geojson_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup_path = BACKUP_DIR / f"{path.stem}.{int(path.stat().st_mtime)}{path.suffix}"
        if not backup_path.exists():
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # print(f"AMAP_JS_KEY: {AMAP_JS_KEY}, AMAP_SECURITY_JS_CODE: {AMAP_SECURITY_JS_CODE}")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "amap_key": AMAP_JS_KEY,
            "amap_security_js_code": AMAP_SECURITY_JS_CODE,
        },
    )


@app.get("/api/polygons", response_model=List[str])
def list_polygons() -> List[str]:
    if not POLYGON_DIR.exists():
        return []
    return sorted([p.name for p in POLYGON_DIR.glob("*.geojson")])


@app.get("/api/polygons/{filename}")
def get_polygon(filename: str):
    _validate_filename(filename)
    path = POLYGON_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), media_type="application/json")


@app.post("/api/polygons/{filename}")
async def save_polygon(filename: str, request: Request):
    _validate_filename(filename)
    path = POLYGON_DIR / filename
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid GeoJSON payload")
    _write_geojson_file(path, data)
    return {"status": "ok", "file": filename}


@app.get("/api/points/{filename}")
def get_points(filename: str):
    _validate_filename(filename)
    if filename.endswith(".geojson"):
        points_name = filename[: -len(".geojson")] + ".points.geojson"
    else:
        points_name = filename + ".points.geojson"
    path = POINTS_DIR / points_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), media_type="application/json")


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
def get_items(filename: str):
    _validate_filename(filename)
    if filename.endswith(".geojson"):
        items_name = filename[: -len(".geojson")] + ".items.geojson"
    else:
        items_name = filename + ".items.geojson"
    path = ITEMS_DIR / items_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), media_type="application/json")


@app.post("/api/items/{filename}")
async def save_items(filename: str, request: Request):
    _validate_filename(filename)
    if filename.endswith(".geojson"):
        items_name = filename[: -len(".geojson")] + ".items.geojson"
    else:
        items_name = filename + ".items.geojson"
    path = ITEMS_DIR / items_name
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid GeoJSON payload")
    _write_geojson_file(path, data)
    return {"status": "ok", "file": items_name}
