"""FastAPI web app for GeoJSON viewer."""

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
AMAP_JS_KEY = os.getenv("AMAP_JS_KEY", "").strip()
AMAP_SECURITY_JS_CODE = os.getenv("AMAP_SECURITY_JS_CODE", "").strip()

app = FastAPI(title="GeoJSON Viewer")

# Static files
app.mount(
    "/static", StaticFiles(directory=BASE_DIR / "app" / "web" / "static"), name="static"
)

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "web" / "templates"))


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
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = POLYGON_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), media_type="application/json")
